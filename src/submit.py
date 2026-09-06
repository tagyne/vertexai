"""Compile and submit the Vertex AI pipeline manually."""

import argparse
import os
from pathlib import Path

from google.cloud import aiplatform
from kfp import compiler

from src.pipeline import student_performance_pipeline


PIPELINE_LABELS = {
    "project": "student-performance-mlops",
    "managed_by": "vertex-pipeline",
    "environment": "dev",
}


def monitoring_uri_from_pipeline_root(pipeline_root: str) -> tuple[str, str]:
    """Derive durable monitoring paths from the documented pipeline root."""
    suffix = "/pipeline-root"
    if not pipeline_root.endswith(suffix):
        raise ValueError(f"pipeline_root must end with {suffix}")
    bucket_root = pipeline_root[: -len(suffix)]
    return (
        f"{bucket_root}/monitoring/baselines/student-performance/latest/train.csv",
        f"{bucket_root}/monitoring/schema/analysis-instance.yaml",
    )


def submit(project: str, region: str, pipeline_root: str,
           endpoint_id: str, service_account: str | None,
           monitoring_notification_channel: str) -> None:
    output_path = Path("pipeline.yaml")
    compiler.Compiler().compile(student_performance_pipeline, str(output_path))
    baseline_uri, schema_uri = monitoring_uri_from_pipeline_root(pipeline_root)
    aiplatform.init(project=project, location=region, staging_bucket=pipeline_root)
    job = aiplatform.PipelineJob(
        display_name="student-performance-pipeline",
        enable_caching=None,
        template_path=str(output_path),
        pipeline_root=pipeline_root,
        labels=PIPELINE_LABELS,
        parameter_values={"project": project,
                          "region": region, "endpoint_id": endpoint_id,
                          "monitoring_baseline_uri": baseline_uri,
                          "monitoring_schema_uri": schema_uri,
                          "monitoring_notification_channel": monitoring_notification_channel},
    )
    job.submit(service_account=service_account)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--region", default=os.getenv("VERTEX_REGION", "europe-west9"))
    parser.add_argument("--pipeline-root", default=os.getenv("PIPELINE_ROOT"))
    parser.add_argument("--endpoint-id", default=os.getenv("VERTEX_ENDPOINT_ID"))
    parser.add_argument("--service-account", default=os.getenv("PIPELINE_SERVICE_ACCOUNT"))
    parser.add_argument("--monitoring-notification-channel", default=os.getenv("MONITORING_NOTIFICATION_CHANNEL"))
    args = parser.parse_args()
    missing = [name for name in ("project", "pipeline_root", "endpoint_id", "monitoring_notification_channel") if not getattr(args, name)]
    if missing:
        parser.error(f"missing required configuration: {', '.join(missing)}")
    submit(args.project, args.region, args.pipeline_root, args.endpoint_id, args.service_account, args.monitoring_notification_channel)


if __name__ == "__main__":
    main()
