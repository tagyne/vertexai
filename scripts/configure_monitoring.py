"""Create or reconcile Model Monitoring for the deployed student model."""

import argparse

from src.monitoring import ensure_monitoring_job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="europe-west9")
    parser.add_argument("--endpoint-id", required=True)
    parser.add_argument("--model-resource-name", required=True)
    parser.add_argument("--baseline-uri", required=True)
    parser.add_argument("--schema-uri", required=True)
    parser.add_argument("--notification-channel", required=True)
    args = parser.parse_args()
    resource_name = ensure_monitoring_job(
        project=args.project,
        region=args.region,
        endpoint_id=args.endpoint_id,
        model_resource_name=args.model_resource_name,
        baseline_uri=args.baseline_uri,
        schema_uri=args.schema_uri,
        notification_channel=args.notification_channel,
    )
    print(resource_name)


if __name__ == "__main__":
    main()
