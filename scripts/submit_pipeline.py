#!/usr/bin/env python3
"""Submit the Vertex AI pipeline using the current Terraform outputs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from src.submit import submit


REQUIRED_OUTPUTS = (
    "ml_bucket_uri",
    "endpoint_id",
    "pipeline_service_account",
    "monitoring_notification_channel",
    "monitoring_baseline_uri",
    "monitoring_schema_uri",
)


def terraform_outputs(raw_output: str) -> dict[str, str]:
    """Parse Terraform's JSON output and unwrap each output value."""
    try:
        decoded: Any = json.loads(raw_output)
    except json.JSONDecodeError as error:
        raise ValueError("Terraform output is not valid JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError("Terraform output must be a JSON object")

    outputs: dict[str, str] = {}
    for name, item in decoded.items():
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            raise ValueError(f"Terraform output {name} must contain a string value")
        outputs[name] = item["value"]
    return outputs


def pipeline_configuration(outputs: dict[str, str]) -> dict[str, str]:
    """Validate Terraform outputs and build the submit arguments."""
    missing = [name for name in REQUIRED_OUTPUTS if not outputs.get(name)]
    if missing:
        raise ValueError(f"Missing Terraform outputs: {', '.join(missing)}")

    bucket_uri = outputs["ml_bucket_uri"].rstrip("/")
    if not bucket_uri.startswith("gs://") or "/" in bucket_uri[5:]:
        raise ValueError("ml_bucket_uri must be a single gs:// bucket URI")

    pipeline_root = f"{bucket_uri}/pipeline-root"
    expected_baseline = f"{bucket_uri}/monitoring/baselines/student-performance/latest/train.csv"
    expected_schema = f"{bucket_uri}/monitoring/schema/analysis-instance.yaml"
    if outputs["monitoring_baseline_uri"] != expected_baseline:
        raise ValueError("Terraform output monitoring_baseline_uri is inconsistent with ml_bucket_uri")
    if outputs["monitoring_schema_uri"] != expected_schema:
        raise ValueError("Terraform output monitoring_schema_uri is inconsistent with ml_bucket_uri")

    return {
        "pipeline_root": pipeline_root,
        "endpoint_id": outputs["endpoint_id"],
        "service_account": outputs["pipeline_service_account"],
        "monitoring_notification_channel": outputs["monitoring_notification_channel"],
    }


def read_terraform_outputs(terraform_dir: Path) -> dict[str, str]:
    """Read Terraform outputs from a working directory."""
    command = ["terraform", f"-chdir={terraform_dir}", "output", "-json"]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise RuntimeError("terraform executable was not found in PATH") from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"Unable to read Terraform outputs: {details}") from error
    return terraform_outputs(result.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--region", default=os.getenv("VERTEX_REGION", "europe-west9"))
    parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "terraform",
    )
    args = parser.parse_args(argv)
    if not args.project:
        parser.error("--project or GOOGLE_CLOUD_PROJECT is required")

    configuration = pipeline_configuration(read_terraform_outputs(args.terraform_dir))
    print(f"Submitting pipeline to {args.project}/{args.region}")
    print(f"Pipeline root: {configuration['pipeline_root']}")
    submit(
        project=args.project,
        region=args.region,
        pipeline_root=configuration["pipeline_root"],
        endpoint_id=configuration["endpoint_id"],
        service_account=configuration["service_account"],
        monitoring_notification_channel=configuration["monitoring_notification_channel"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
