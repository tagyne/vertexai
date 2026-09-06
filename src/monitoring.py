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
