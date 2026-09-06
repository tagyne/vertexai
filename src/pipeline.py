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


@dsl.component(base_image="python:3.11", packages_to_install=["google-cloud-aiplatform==1.71.1"])
def register_model(model: dsl.Input[dsl.Model], project: str, region: str, model_display_name: str, model_resource_name: dsl.OutputPath(str)) -> None:
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


@dsl.component(base_image="python:3.11", packages_to_install=["google-cloud-aiplatform==1.71.1"])
def deploy_model(model_resource_name: str, project: str, region: str, endpoint_id: str) -> None:
    """Deploy the registered model to the Terraform-owned stable endpoint."""
    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region)
    model = aiplatform.Model(model_name=model_resource_name)
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_id)
    model.deploy(endpoint=endpoint, machine_type="e2-standard-4", min_replica_count=1, max_replica_count=1)


@dsl.component(base_image="python:3.11", packages_to_install=["google-cloud-aiplatform==1.71.1"])
def configure_monitoring(
    model_resource_name: str,
    project: str,
    region: str,
    endpoint_id: str,
    baseline_uri: str,
    schema_uri: str,
    notification_channel: str,
) -> None:
    """Create or update Model Monitoring for the deployed model."""
    from google.cloud import aiplatform
    from google.cloud.aiplatform import model_monitoring

    monitored_features = [
        "gender", "parental_education", "internet_access",
        "extracurricular_activities", "part_time_job", "study_time_hours",
        "attendance_percent", "sleep_hours", "previous_grade",
    ]
    endpoint_resource = endpoint_id if endpoint_id.startswith("projects/") else (
        f"projects/{project}/locations/{region}/endpoints/{endpoint_id}"
    )
    aiplatform.init(project=project, location=region)
    endpoint = aiplatform.Endpoint(endpoint_resource)
    deployed_model_id = next(
        (model.id for model in endpoint.list_models() if model.model == model_resource_name),
        None,
    )
    if deployed_model_id is None:
        raise ValueError(f"Model {model_resource_name} is not deployed on the endpoint")
    objective = model_monitoring.ObjectiveConfig(
        skew_detection_config=model_monitoring.SkewDetectionConfig(
            data_source=baseline_uri,
            data_format="csv",
            target_field="final_exam_score",
            skew_thresholds=0.2,
        ),
        drift_detection_config=model_monitoring.DriftDetectionConfig(
            drift_thresholds={feature: 0.2 for feature in monitored_features},
        ),
    )
    schedule = model_monitoring.ScheduleConfig(monitor_interval=24)
    sampling = model_monitoring.RandomSampleConfig(sample_rate=0.5)
    alert = model_monitoring.AlertConfig(
        enable_logging=True,
        notification_channels=[notification_channel],
    )
    labels = {
        "project": "student-performance-mlops",
        "managed_by": "vertex-pipeline",
        "environment": "dev",
    }
    jobs = aiplatform.ModelDeploymentMonitoringJob.list(
        filter='display_name="student-performance-monitoring"',
        project=project,
        location=region,
    )
    if jobs:
        jobs[0].update(
            objective_configs=objective,
            deployed_model_ids=[deployed_model_id],
            schedule_config=schedule,
            logging_sampling_strategy=sampling,
            alert_config=alert,
            labels=labels,
        )
    else:
        aiplatform.ModelDeploymentMonitoringJob.create(
            endpoint=endpoint,
            objective_configs=objective,
            deployed_model_ids=[deployed_model_id],
            logging_sampling_strategy=sampling,
            schedule_config=schedule,
            display_name="student-performance-monitoring",
            alert_config=alert,
            analysis_instance_schema_uri=schema_uri,
            labels=labels,
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
        project=project,
        region=region,
        endpoint_id=endpoint_id,
        baseline_uri=monitoring_baseline_uri,
        schema_uri=monitoring_schema_uri,
        notification_channel=monitoring_notification_channel,
    )
    monitoring.set_caching_options(False)
    monitoring.after(deploy)
