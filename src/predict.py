"""Prediction contract and optional Vertex AI endpoint client."""

from typing import Any

from google.cloud import aiplatform

from src.data import CATEGORICAL_FEATURES, NUMERICAL_FEATURES

PREDICTION_FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES


def parse_prediction_request(payload: dict[str, Any]) -> list[dict[str, Any]]:
    instances = payload.get("instances")
    if not isinstance(instances, list) or not instances:
        raise ValueError("instances must be a non-empty list")
    for instance in instances:
        if not isinstance(instance, dict):
            raise ValueError("Each instance must be an object")
        missing = [feature for feature in PREDICTION_FEATURES if feature not in instance]
        if missing:
            raise ValueError(f"Missing prediction features: {', '.join(missing)}")
        extra = sorted(set(instance) - set(PREDICTION_FEATURES))
        if extra:
            raise ValueError(f"Unexpected prediction features: {', '.join(extra)}")
    return instances


def format_prediction_response(predictions: list[float]) -> dict[str, list[dict[str, float]]]:
    return {"predictions": [{"predicted_final_exam_score": float(value)} for value in predictions]}


def predict_endpoint(
    project: str, region: str, endpoint_id: str, instances: list[dict[str, Any]]
) -> dict[str, list[dict[str, float]]]:
    """Call an existing endpoint after validating the raw feature contract."""
    validated_instances = parse_prediction_request({"instances": instances})
    aiplatform.init(project=project, location=region)
    endpoint = aiplatform.Endpoint(endpoint_id=endpoint_id)
    response = endpoint.predict(instances=validated_instances)
    return format_prediction_response([float(value) for value in response.predictions])
