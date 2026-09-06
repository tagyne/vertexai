import json

import pytest

from scripts.submit_pipeline import pipeline_configuration, terraform_outputs


def test_terraform_outputs_are_unwrapped_and_pipeline_root_is_derived() -> None:
    raw = json.dumps(
        {
            "ml_bucket_uri": {"value": "gs://ml-bucket"},
            "endpoint_id": {"value": "projects/p/locations/e/endpoints/ep"},
            "pipeline_service_account": {"value": "pipeline@p.iam.gserviceaccount.com"},
            "monitoring_notification_channel": {"value": "projects/p/notificationChannels/1"},
            "monitoring_baseline_uri": {
                "value": "gs://ml-bucket/monitoring/baselines/student-performance/latest/train.csv"
            },
            "monitoring_schema_uri": {
                "value": "gs://ml-bucket/monitoring/schema/analysis-instance.yaml"
            },
        }
    )

    outputs = terraform_outputs(raw)

    assert pipeline_configuration(outputs) == {
        "pipeline_root": "gs://ml-bucket/pipeline-root",
        "endpoint_id": "projects/p/locations/e/endpoints/ep",
        "service_account": "pipeline@p.iam.gserviceaccount.com",
        "monitoring_notification_channel": "projects/p/notificationChannels/1",
    }


def test_pipeline_configuration_rejects_inconsistent_monitoring_output() -> None:
    outputs = {
        "ml_bucket_uri": "gs://ml-bucket",
        "endpoint_id": "ep",
        "pipeline_service_account": "pipeline@p.iam.gserviceaccount.com",
        "monitoring_notification_channel": "projects/p/notificationChannels/1",
        "monitoring_baseline_uri": "gs://other-bucket/baseline.csv",
        "monitoring_schema_uri": "gs://ml-bucket/monitoring/schema/analysis-instance.yaml",
    }

    with pytest.raises(ValueError, match="monitoring_baseline_uri"):
        pipeline_configuration(outputs)


def test_terraform_outputs_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="JSON"):
        terraform_outputs("not-json")
