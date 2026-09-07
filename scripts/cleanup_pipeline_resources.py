#!/usr/bin/env python3
"""Delete dynamic resources produced by the student-performance pipeline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import google.cloud.aiplatform as aiplatform
from google.api_core.exceptions import NotFound
from google.cloud import storage
from google.cloud.aiplatform_v1 import MetadataServiceClient

PROJECT_LABELS = {"project": "student-performance-mlops", "managed_by": "vertex-pipeline", "environment": "dev"}
PIPELINE_NAME = "student-performance-pipeline"
PIPELINE_BILLING_LABEL = "vertex-ai-pipelines-run-billing-id"
PIPELINE_TERMINAL_STATES = {"PIPELINE_STATE_SUCCEEDED", "PIPELINE_STATE_FAILED", "PIPELINE_STATE_CANCELLED"}
JOB_TERMINAL_STATES = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED"}


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


@dataclass
class CleanupPlan:
    pipelines: list[Any] = field(default_factory=list)
    custom_jobs: list[Any] = field(default_factory=list)
    models: list[Any] = field(default_factory=list)
    metadata_contexts: set[str] = field(default_factory=set)
    metadata_executions: set[str] = field(default_factory=set)
    metadata_artifacts: set[str] = field(default_factory=set)
    buckets: list[Any] = field(default_factory=list)


def state_name(resource: Any) -> str:
    value = resource.state
    if isinstance(value, str):
        return value.rsplit(".", 1)[-1]
    field = resource._gca_resource._pb.DESCRIPTOR.fields_by_name["state"]
    return field.enum_type.values_by_number[int(value)].name


def has_project_labels(resource: Any) -> bool:
    labels = getattr(resource, "labels", {}) or {}
    return all(labels.get(key) == value for key, value in PROJECT_LABELS.items())


def collect_plan(project: str, region: str) -> CleanupPlan:
    aiplatform.init(project=project, location=region)
    plan = CleanupPlan()
    for job in aiplatform.PipelineJob.list(project=project, location=region):
        labels = getattr(job, "labels", {}) or {}
        if getattr(job, "display_name", "") != PIPELINE_NAME:
            continue
        if not (has_project_labels(job) or labels.get(PIPELINE_BILLING_LABEL)):
            continue
        if state_name(job) not in PIPELINE_TERMINAL_STATES:
            continue
        plan.pipelines.append(job)
        detail = getattr(getattr(job, "_gca_resource", None), "job_detail", None)
        for attribute in ("pipeline_context", "pipeline_run_context"):
            context = getattr(detail, attribute, None) if detail else None
            context_name = getattr(context, "name", "") if context else ""
            if context_name:
                plan.metadata_contexts.add(context_name)

    metadata_client = MetadataServiceClient(
        client_options={"api_endpoint": f"{region}-aiplatform.googleapis.com"}
    )
    metadata_parent = f"projects/{project}/locations/{region}/metadataStores/default"
    for context in metadata_client.list_contexts(parent=metadata_parent):
        context_id = context.name.rsplit("/", 1)[-1]
        if context_id.startswith(PIPELINE_NAME):
            plan.metadata_contexts.add(context.name)
    for context_name in plan.metadata_contexts:
        lineage = metadata_client.query_context_lineage_subgraph(context=context_name)
        plan.metadata_executions.update(execution.name for execution in lineage.executions)
        plan.metadata_artifacts.update(artifact.name for artifact in lineage.artifacts)

    for job in aiplatform.CustomJob.list(project=project, location=region):
        labels = getattr(job, "labels", {}) or {}
        if not labels.get(PIPELINE_BILLING_LABEL) or "vertex_pipelines" not in labels:
            continue
        if state_name(job) in JOB_TERMINAL_STATES:
            plan.custom_jobs.append(job)
    plan.models = [
        model for model in aiplatform.Model.list(project=project, location=region) if has_project_labels(model)
    ]
    storage_client = storage.Client(project=project)
    plan.buckets = [bucket for bucket in storage_client.list_buckets(project=project) if has_project_labels(bucket)]
    return plan


def print_plan(plan: CleanupPlan, project: str, region: str) -> None:
    print(f"Cleanup targets in project={project}, region={region}:")
    print(f"- completed pipeline jobs: {len(plan.pipelines)}")
    print(f"- completed custom training jobs: {len(plan.custom_jobs)}")
    print(f"- pipeline metadata contexts: {len(plan.metadata_contexts)}")
    print(f"- metadata executions: {len(plan.metadata_executions)}")
    print(f"- metadata artifacts: {len(plan.metadata_artifacts)}")
    print(f"- labeled model resources: {len(plan.models)}")
    print(f"- labeled ML buckets (pipeline-root/ and pipeline-tmp/ only): {len(plan.buckets)}")
    print("Protected: Terraform backend, service account, IAM, and stable endpoint.")


def delete_plan(plan: CleanupPlan, project: str, region: str) -> None:
    for start in range(0, len(plan.pipelines), 32):
        batch = plan.pipelines[start : start + 32]
        if batch:
            print(f"Deleting {len(batch)} pipeline job(s)")
            batch[0].batch_delete(
                project=project, location=region, names=[job.resource_name for job in batch]
            )
    metadata_client = MetadataServiceClient(
        client_options={"api_endpoint": f"{region}-aiplatform.googleapis.com"}
    )
    for execution_name in sorted(plan.metadata_executions):
        print(f"Deleting metadata execution: {execution_name}")
        try:
            metadata_client.delete_execution(name=execution_name).result()
        except NotFound:
            pass
    for artifact_name in sorted(plan.metadata_artifacts):
        print(f"Deleting metadata artifact: {artifact_name}")
        try:
            metadata_client.delete_artifact(name=artifact_name).result()
        except NotFound:
            pass
    for context_name in sorted(plan.metadata_contexts, key=lambda value: value.count("/"), reverse=True):
        print(f"Deleting metadata context: {context_name}")
        try:
            metadata_client.delete_context(name=context_name).result()
        except NotFound:
            print(f"Metadata context already absent: {context_name}")
    for job in plan.custom_jobs:
        print(f"Deleting custom job: {job.resource_name}")
        job.delete()
    for model in plan.models:
        print(f"Deleting model: {model.resource_name}")
        model.delete()
    storage_client = storage.Client(project=project)
    for bucket in plan.buckets:
        for prefix in ("pipeline-root/", "pipeline-tmp/"):
            for blob in storage_client.list_blobs(bucket.name, prefix=prefix, versions=True):
                try:
                    bucket.delete_blob(blob.name, generation=blob.generation)
                except NotFound:
                    pass
    print("Cleanup completed. Terraform-owned resources and the stable endpoint were not touched.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--region", default=os.getenv("VERTEX_REGION"))
    parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "terraform",
        help="Terraform working directory",
    )
    parser.add_argument("--execute", action="store_true", help="delete after explicit confirmation")
    args = parser.parse_args()
    try:
        outputs = read_terraform_outputs(args.terraform_dir)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))

    project = args.project or outputs.get("project_id")
    region = args.region or outputs.get("region")
    if not project or not region:
        parser.error("Terraform outputs project_id and region are required")

    plan = collect_plan(project, region)
    print_plan(plan, project, region)
    if not args.execute:
        print("Simulation only. Re-run with --execute to delete after review.")
        return 0
    if input("Type DELETE to confirm: ") != "DELETE":
        print("Cleanup cancelled.")
        return 0
    delete_plan(plan, project, region)
    return 0


if __name__ == "__main__":
    sys.exit(main())
