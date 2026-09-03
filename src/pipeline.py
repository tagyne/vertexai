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
    if frame[required].isna().any().any():
        raise ValueError("Dataset contains missing values in required columns")
    selected = frame[categorical + numerical + ["final_exam_score"]]
    train, test = train_test_split(selected, test_size=0.2, random_state=42)
    train.to_csv(train_dataset.path, index=False)
    test.to_csv(test_dataset.path, index=False)


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
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("numerical", "passthrough", numerical),
        ])),
        ("regressor", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
    ])
    estimator.fit(frame[categorical + numerical], frame["final_exam_score"])
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
    endpoint = aiplatform.Endpoint(endpoint_id=endpoint_id)
    model.deploy(endpoint=endpoint, machine_type="n1-standard-4", min_replica_count=1, max_replica_count=1)


@dsl.pipeline(name="student-performance-pipeline")
def student_performance_pipeline(project: str, region: str, endpoint_id: str, model_display_name: str = "student-performance") -> None:
    raw = download_dataset(project=project)
    prepared = prepare_data(raw_dataset=raw.outputs["dataset"])
    trained = train_model(train_dataset=prepared.outputs["train_dataset"])
    evaluated = evaluate_model(test_dataset=prepared.outputs["test_dataset"], model=trained.outputs["model"])
    registered = register_model(model=trained.outputs["model"], project=project, region=region, model_display_name=model_display_name)
    deploy = deploy_model(model_resource_name=registered.outputs["model_resource_name"], project=project, region=region, endpoint_id=endpoint_id)
    deploy.after(evaluated)
