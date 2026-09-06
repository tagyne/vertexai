"""Vertex AI Model Monitoring configuration and reconciliation helpers."""

from typing import Any


MONITORING_JOB_DISPLAY_NAME = "student-performance-monitoring"
MONITORED_FEATURES = (
    "gender",
    "parental_education",
    "internet_access",
    "extracurricular_activities",
    "part_time_job",
    "study_time_hours",
    "attendance_percent",
    "sleep_hours",
    "previous_grade",
)
DEFAULT_DRIFT_THRESHOLD = 0.2


def endpoint_resource_name(project: str, region: str, endpoint_id: str) -> str:
    """Return a canonical Vertex AI endpoint resource name."""
    if endpoint_id.startswith("projects/"):
        return endpoint_id
    return f"projects/{project}/locations/{region}/endpoints/{endpoint_id}"


def find_deployed_model_id(
    deployed_models: list[dict[str, Any]], model_resource_name: str
) -> str:
    """Find the endpoint deployment ID for a registered model."""
    for deployed_model in deployed_models:
        if deployed_model.get("model") == model_resource_name:
            model_id = deployed_model.get("id")
            if model_id:
                return str(model_id)
    raise ValueError(f"Model {model_resource_name} is not deployed on the endpoint")


def _thresholds() -> dict[str, dict[str, float]]:
    return {feature: {"value": DEFAULT_DRIFT_THRESHOLD} for feature in MONITORED_FEATURES}


def build_monitoring_job_payload(
    endpoint_resource_name: str,
    deployed_model_id: str,
    baseline_uri: str,
    schema_uri: str,
    notification_channel: str,
) -> dict[str, Any]:
    """Build the v1 ModelDeploymentMonitoringJob request body."""
    thresholds = _thresholds()
    return {
        "displayName": MONITORING_JOB_DISPLAY_NAME,
        "endpoint": endpoint_resource_name,
        "modelDeploymentMonitoringObjectiveConfigs": [
            {
                "deployedModelId": deployed_model_id,
                "objectiveConfig": {
                    "trainingDataset": {
                        "dataFormat": "csv",
                        "gcsSource": {"uris": [baseline_uri]},
                        "targetField": "final_exam_score",
                    },
                    "trainingPredictionSkewDetectionConfig": {
                        "skewThresholds": thresholds,
                    },
                    "predictionDriftDetectionConfig": {
                        "driftThresholds": _thresholds(),
                    },
                },
            }
        ],
        "loggingSamplingStrategy": {
            "randomSampleConfig": {"sampleRate": 0.5},
        },
        "modelDeploymentMonitoringScheduleConfig": {
            "monitorInterval": {"seconds": 86400},
        },
        "modelMonitoringAlertConfig": {
            "enableLogging": True,
            "notificationChannels": [notification_channel],
        },
        "analysisInstanceSchemaUri": schema_uri,
        "labels": {
            "project": "student-performance-mlops",
            "managed_by": "vertex-pipeline",
            "environment": "dev",
        },
    }


def ensure_monitoring_job(
    project: str,
    region: str,
    endpoint_id: str,
    model_resource_name: str,
    baseline_uri: str,
    schema_uri: str,
    notification_channel: str,
) -> str:
    """Create or update the monitoring job for the currently deployed model."""
    from google.cloud import aiplatform
    from google.cloud.aiplatform import model_monitoring

    aiplatform.init(project=project, location=region)
    endpoint = aiplatform.Endpoint(endpoint_resource_name(project, region, endpoint_id))
    deployed_model_id = find_deployed_model_id(
        [{"id": model.id, "model": model.model} for model in endpoint.list_models()],
        model_resource_name,
    )
    objective = model_monitoring.ObjectiveConfig(
        skew_detection_config=model_monitoring.SkewDetectionConfig(
            data_source=baseline_uri,
            data_format="csv",
            target_field="final_exam_score",
            skew_thresholds=DEFAULT_DRIFT_THRESHOLD,
        ),
        drift_detection_config=model_monitoring.DriftDetectionConfig(
            drift_thresholds={feature: DEFAULT_DRIFT_THRESHOLD for feature in MONITORED_FEATURES},
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
        filter=f'display_name="{MONITORING_JOB_DISPLAY_NAME}"',
        project=project,
        location=region,
    )
    if jobs:
        job = jobs[0]
        job.update(
            objective_configs=objective,
            deployed_model_ids=[deployed_model_id],
            schedule_config=schedule,
            logging_sampling_strategy=sampling,
            alert_config=alert,
            labels=labels,
        )
    else:
        job = aiplatform.ModelDeploymentMonitoringJob.create(
            endpoint=endpoint,
            objective_configs=objective,
            deployed_model_ids=[deployed_model_id],
            logging_sampling_strategy=sampling,
            schedule_config=schedule,
            display_name=MONITORING_JOB_DISPLAY_NAME,
            alert_config=alert,
            analysis_instance_schema_uri=schema_uri,
            labels=labels,
        )
    return job.resource_name
