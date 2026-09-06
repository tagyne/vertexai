import pytest

from src.submit import monitoring_uri_from_pipeline_root


def test_monitoring_uris_are_derived_from_pipeline_bucket() -> None:
    baseline_uri, schema_uri = monitoring_uri_from_pipeline_root(
        "gs://student-performance-mlops-p/pipeline-root"
    )

    assert baseline_uri == "gs://student-performance-mlops-p/monitoring/baselines/student-performance/latest/train.csv"
    assert schema_uri == "gs://student-performance-mlops-p/monitoring/schema/analysis-instance.yaml"


def test_monitoring_uris_require_pipeline_root_convention() -> None:
    with pytest.raises(ValueError, match="pipeline-root"):
        monitoring_uri_from_pipeline_root("gs://bucket/artifacts")
