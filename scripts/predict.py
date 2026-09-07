#!/usr/bin/env python3
"""Send a JSON prediction request to a deployed Vertex AI endpoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def access_token() -> str:
    """Return an access token from the active gcloud account."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("gcloud is required but was not found in PATH") from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"Unable to retrieve gcloud access token: {details}") from error

    token = result.stdout.strip()
    if not token:
        raise RuntimeError("gcloud returned an empty access token")
    return token


def terraform_configuration(terraform_dir: Path) -> dict[str, str]:
    """Read the project, region, and endpoint from Terraform outputs."""
    try:
        result = subprocess.run(
            ["terraform", f"-chdir={terraform_dir}", "output", "-json"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("terraform is required but was not found in PATH") from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"Unable to read Terraform outputs: {details}") from error

    try:
        outputs: Any = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Terraform output is not valid JSON") from error

    required = ("project_id", "region", "endpoint_id")
    configuration: dict[str, str] = {}
    for name in required:
        value = outputs.get(name, {}).get("value") if isinstance(outputs, dict) else None
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"Terraform output {name} is missing or is not a string")
        configuration[name] = value
    return configuration


def predict(
    input_file: Path,
    project_id: str,
    region: str,
    endpoint_id: str,
) -> str:
    """Send the input JSON to Vertex AI and return the response body."""
    try:
        payload = input_file.read_bytes()
    except OSError as error:
        raise RuntimeError(f"Unable to read input file {input_file}: {error}") from error

    try:
        json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Input file is not valid JSON: {error}") from error

    encoded_endpoint_id = quote(endpoint_id, safe="")
    url = (
        f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{region}/endpoints/{encoded_endpoint_id}:predict"
    )
    request = Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request) as response:
            return response.read().decode("utf-8")
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Vertex AI returned HTTP {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError(f"Unable to reach Vertex AI: {error.reason}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    project_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "input_file",
        type=Path,
        nargs="?",
        default=project_root / "input.json",
        help="JSON file sent to the endpoint (default: input.json)",
    )
    parser.add_argument("--project-id", default=os.getenv("PROJECT_ID"))
    parser.add_argument("--region", default=os.getenv("REGION"))
    parser.add_argument("--endpoint-id", default=os.getenv("ENDPOINT_ID"))
    parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "terraform",
        help="Terraform working directory",
    )
    args = parser.parse_args()

    if not args.input_file.is_file():
        parser.error(f"Input file not found: {args.input_file}")

    try:
        configuration = terraform_configuration(args.terraform_dir)
        project_id = args.project_id or configuration["project_id"]
        region = args.region or configuration["region"]
        endpoint_id = args.endpoint_id or configuration["endpoint_id"]
        print(predict(args.input_file, project_id, region, endpoint_id))
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
