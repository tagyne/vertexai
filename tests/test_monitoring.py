import pytest

from src.monitoring import (
    find_deployed_model_id,
)
from src.submit import monitoring_uri_from_pipeline_root


def test_find_deployed_model_id_matches_registered_model() -> None:
    deployed_models = [
        {"id": "111", "model": "projects/p/locations/eu/models/old"},
        {"id": "222", "model": "projects/p/locations/eu/models/new"},
    ]

    assert find_deployed_model_id(deployed_models, "projects/p/locations/eu/models/new") == "222"


def test_find_deployed_model_id_fails_when_model_is_not_deployed() -> None:
    with pytest.raises(ValueError, match="not deployed"):
        find_deployed_model_id([], "projects/p/locations/eu/models/new")


def test_monitoring_uris_are_derived_from_pipeline_bucket() -> None:
    baseline_uri, schema_uri = monitoring_uri_from_pipeline_root(
        "gs://student-performance-mlops-p/pipeline-root"
    )

    assert baseline_uri == "gs://student-performance-mlops-p/monitoring/baselines/student-performance/latest/train.csv"
    assert schema_uri == "gs://student-performance-mlops-p/monitoring/schema/analysis-instance.yaml"


def test_monitoring_uris_require_pipeline_root_convention() -> None:
    with pytest.raises(ValueError, match="pipeline-root"):
        monitoring_uri_from_pipeline_root("gs://bucket/artifacts")
