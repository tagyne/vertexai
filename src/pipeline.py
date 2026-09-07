"""Six-stage Vertex AI Pipeline definition."""

from kfp import dsl


@dsl.component(base_image="python:3.11", packages_to_install=[
    "google-cloud-secret-manager==2.22.0", "kagglehub==1.0.2",
])
def download_dataset(project: str, dataset: dsl.Output[dsl.Dataset]) -> None:
    """Download the public Kaggle dataset into a pipeline artifact."""
    import shutil
    from pathlib import Path
    import os
    from google.cloud import secretmanager
    import kagglehub

    client = secretmanager.SecretManagerServiceClient()

    def read_secret(secret_id: str) -> str:
        response = client.access_secret_version(
            name=f"projects/{project}/secrets/{secret_id}/versions/latest",
        )
        return response.payload.data.decode("utf-8")

    os.environ["KAGGLE_USERNAME"] = read_secret("kaggle-username")
    os.environ["KAGGLE_KEY"] = read_secret("kaggle-key")
    downloaded = Path(kagglehub.dataset_download(
        "harshadapatil31/student-performance-and-study-habits-dataset",
    ))
    csv_files = list(downloaded.rglob("*.csv")) if downloaded.is_dir() else [downloaded]
    if len(csv_files) != 1:
        raise ValueError(f"Expected exactly one CSV in Kaggle dataset, found {len(csv_files)}")
    shutil.copyfile(csv_files[0], dataset.path)


@dsl.component(base_image="python:3.11", packages_to_install=["pandas==2.2.3", "scikit-learn==1.5.2"])
def prepare_data(raw_dataset: dsl.Input[dsl.Dataset], train_dataset: dsl.Output[dsl.Dataset], test_dataset: dsl.Output[dsl.Dataset]) -> None:
    """Validate, remove leakage, and create deterministic train/test datasets."""
    import pandas as pd
    from sklearn.model_selection import train_test_split

    categorical = ["gender", "parental_education", "internet_access", "extracurricular_activities", "part_time_job"]
    numerical = ["study_time_hours", "attendance_percent", "sleep_hours", "previous_grade"]
    required = ["student_id", *categorical, *numerical, "final_exam_score", "final_grade"]
    frame = pd.read_csv(raw_dataset.path)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    frame[categorical] = frame[categorical].fillna("Unknown")
    non_imputable = ["student_id", *numerical, "final_exam_score", "final_grade"]
    if frame[non_imputable].isna().any().any():
        raise ValueError("Dataset contains missing values in required columns")
    selected = frame[categorical + numerical + ["final_exam_score"]]
    train, test = train_test_split(selected, test_size=0.2, random_state=42)
    train.to_csv(train_dataset.path, index=False)
    test.to_csv(test_dataset.path, index=False)


@dsl.component(base_image="python:3.11", packages_to_install=["google-cloud-storage==2.18.2"])
def publish_baseline(train_dataset: dsl.Input[dsl.Dataset], baseline_uri: str) -> None:
    """Publish the training data at a durable URI used by Model Monitoring."""
    from google.cloud import storage

    if not baseline_uri.startswith("gs://"):
        raise ValueError("baseline_uri must be a gs:// URI")
    bucket_name, object_name = baseline_uri[5:].split("/", 1)
    storage.Client().bucket(bucket_name).blob(object_name).upload_from_filename(
        train_dataset.path, content_type="text/csv"
    )


@dsl.component(base_image="python:3.11", packages_to_install=["joblib==1.4.2", "pandas==2.2.3", "scikit-learn==1.5.2"])
def train_model(train_dataset: dsl.Input[dsl.Dataset], model: dsl.Output[dsl.Model]) -> None:
    """Train and serialize the preprocessing and regression pipeline."""
    from pathlib import Path
    import joblib
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    categorical = ["gender", "parental_education", "internet_access", "extracurricular_activities", "part_time_job"]
    numerical = ["study_time_hours", "attendance_percent", "sleep_hours", "previous_grade"]
    frame = pd.read_csv(train_dataset.path)
    estimator = Pipeline([
        ("preprocessor", ColumnTransformer([
            ("categorical", OneHotEncoder(handle_unknown="ignore"), list(range(len(categorical)))),
            ("numerical", "passthrough", list(range(len(categorical), len(categorical) + len(numerical)))),
        ])),
        ("regressor", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
    ])
    estimator.fit(frame[categorical + numerical].to_numpy(), frame["final_exam_score"])
    model_dir = Path(model.path)
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(estimator, model_dir / "model.joblib")


@dsl.component(base_image="python:3.11", packages_to_install=["joblib==1.4.2", "pandas==2.2.3", "scikit-learn==1.5.2"])
def evaluate_model(test_dataset: dsl.Input[dsl.Dataset], model: dsl.Input[dsl.Model], metrics: dsl.Output[dsl.Metrics]) -> None:
    """Evaluate the trained model and publish MAE/RMSE metrics."""
    import joblib
    import pandas as pd
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    categorical = ["gender", "parental_education", "internet_access", "extracurricular_activities", "part_time_job"]
    numerical = ["study_time_hours", "attendance_percent", "sleep_hours", "previous_grade"]
    frame = pd.read_csv(test_dataset.path)
    estimator = joblib.load(f"{model.path}/model.joblib")
    predictions = estimator.predict(frame[categorical + numerical])
    metrics.log_metric("mae", float(mean_absolute_error(frame["final_exam_score"], predictions)))
    metrics.log_metric("rmse", float(mean_squared_error(frame["final_exam_score"], predictions) ** 0.5))


@dsl.component(base_image="python:3.11", packages_to_install=["google-cloud-aiplatform==1.153.1"])
def register_model(
    model: dsl.Input[dsl.Model],
    project: str,
    region: str,
    model_display_name: str,
    model_resource_name: dsl.OutputPath(str),
    model_version_id: dsl.OutputPath(str),
) -> None:
    """Register the trained artifact in Vertex AI Model Registry."""
    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region)
    registered = aiplatform.Model.upload(
        display_name=model_display_name, artifact_uri=model.uri,
        labels={"project": "student-performance-mlops", "managed_by": "vertex-pipeline", "environment": "dev"},
        serving_container_image_uri="europe-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-5:latest",
    )
    with open(model_resource_name, "w", encoding="utf-8") as output:
        output.write(registered.resource_name)
    with open(model_version_id, "w", encoding="utf-8") as output:
        output.write(registered.version_id)


@dsl.component(base_image="python:3.11", packages_to_install=["google-cloud-aiplatform==1.153.1"])
def deploy_model(model_resource_name: str, project: str, region: str, endpoint_id: str) -> None:
    """Deploy the registered model to the Terraform-owned stable endpoint."""
    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region)
    model = aiplatform.Model(model_name=model_resource_name)
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_id)
    model.deploy(endpoint=endpoint, machine_type="e2-standard-4", min_replica_count=1, max_replica_count=1)


@dsl.component(base_image="python:3.11", packages_to_install=["google-cloud-aiplatform==1.153.1"])
def configure_monitoring(
    model_resource_name: str,
    model_version_id: str,
    project: str,
    region: str,
    endpoint_id: str,
    baseline_uri: str,
    notification_channel: str,
) -> None:
    """Create a Model Monitoring v2 monitor and a one-minute schedule."""
    from google.cloud import aiplatform
    from vertexai.resources.preview import ml_monitoring

    endpoint_resource = endpoint_id if endpoint_id.startswith("projects/") else (
        f"projects/{project}/locations/{region}/endpoints/{endpoint_id}"
    )
    aiplatform.init(project=project, location=region)
    schema = ml_monitoring.spec.ModelMonitoringSchema(
        feature_fields=[
            ml_monitoring.spec.FieldSchema(name="gender", data_type="string"),
            ml_monitoring.spec.FieldSchema(name="parental_education", data_type="string"),
            ml_monitoring.spec.FieldSchema(name="internet_access", data_type="string"),
            ml_monitoring.spec.FieldSchema(name="extracurricular_activities", data_type="string"),
            ml_monitoring.spec.FieldSchema(name="part_time_job", data_type="string"),
            ml_monitoring.spec.FieldSchema(name="study_time_hours", data_type="float"),
            ml_monitoring.spec.FieldSchema(name="attendance_percent", data_type="float"),
            ml_monitoring.spec.FieldSchema(name="sleep_hours", data_type="float"),
            ml_monitoring.spec.FieldSchema(name="previous_grade", data_type="float"),
        ],
        prediction_fields=[
            ml_monitoring.spec.FieldSchema(
                name="predicted_final_exam_score", data_type="float"
            ),
        ],
    )
    training_dataset = ml_monitoring.spec.MonitoringInput(
        gcs_uri=baseline_uri,
        data_format="csv",
    )
    target_dataset = ml_monitoring.spec.MonitoringInput(
        endpoints=[endpoint_resource],
        window="1h",
    )
    drift = ml_monitoring.spec.DataDriftSpec(
        categorical_metric_type="l_infinity",
        numeric_metric_type="jensen_shannon_divergence",
        default_categorical_alert_threshold=0.2,
        default_numeric_alert_threshold=0.2,
    )
    objective = ml_monitoring.spec.TabularObjective(
        feature_drift_spec=drift,
        prediction_output_drift_spec=drift,
    )
    notification = ml_monitoring.spec.NotificationSpec(
        notification_channels=[notification_channel],
        enable_cloud_logging=True,
    )
    output_spec = ml_monitoring.spec.OutputSpec(
        gcs_base_dir=baseline_uri.rsplit("/monitoring/", 1)[0] + "/monitoring/v2-results"
    )
    monitor = ml_monitoring.ModelMonitor.create(
        display_name="student-performance-monitor",
        model_name=model_resource_name,
        model_version_id=model_version_id,
        model_monitoring_schema=schema,
        training_dataset=training_dataset,
        tabular_objective_spec=objective,
        output_spec=output_spec,
        notification_spec=notification,
    )
    monitor.create_schedule(
        cron="* * * * *",
        target_dataset=target_dataset,
        display_name="student-performance-monitoring-minute",
        model_monitoring_job_display_name="student-performance-monitoring-minute",
        tabular_objective_spec=objective,
        notification_spec=notification,
        output_spec=output_spec,
    )


@dsl.pipeline(name="student-performance-pipeline")
def student_performance_pipeline(
    project: str,
    region: str,
    endpoint_id: str,
    monitoring_baseline_uri: str = "",
    monitoring_schema_uri: str = "",
    monitoring_notification_channel: str = "",
    model_display_name: str = "student-performance",
) -> None:
    raw = download_dataset(project=project)
    prepared = prepare_data(raw_dataset=raw.outputs["dataset"])
    baseline = publish_baseline(
        train_dataset=prepared.outputs["train_dataset"],
        baseline_uri=monitoring_baseline_uri,
    )
    baseline.set_caching_options(False)
    trained = train_model(train_dataset=prepared.outputs["train_dataset"])
    evaluated = evaluate_model(test_dataset=prepared.outputs["test_dataset"], model=trained.outputs["model"])
    registered = register_model(model=trained.outputs["model"], project=project, region=region, model_display_name=model_display_name)
    registered.set_caching_options(False)
    deploy = deploy_model(model_resource_name=registered.outputs["model_resource_name"], project=project, region=region, endpoint_id=endpoint_id)
    deploy.set_caching_options(False)
    deploy.after(evaluated)
    monitoring = configure_monitoring(
        model_resource_name=registered.outputs["model_resource_name"],
        model_version_id=registered.outputs["model_version_id"],
        project=project,
        region=region,
        endpoint_id=endpoint_id,
        baseline_uri=monitoring_baseline_uri,
        notification_channel=monitoring_notification_channel,
    )
    monitoring.set_caching_options(False)
    monitoring.after(deploy)
