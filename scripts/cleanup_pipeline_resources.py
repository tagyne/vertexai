#!/usr/bin/env python3
"""Delete dynamic resources produced by the student-performance pipeline."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
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


@dataclass
class CleanupPlan:
    pipelines: list[Any] = field(default_factory=list)
    custom_jobs: list[Any] = field(default_factory=list)
    models: list[Any] = field(default_factory=list)
    metadata_contexts: set[str] = field(default_factory=set)
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
    pipeline_billing_ids: set[str] = set()
    for job in aiplatform.PipelineJob.list(project=project, location=region):
        labels = getattr(job, "labels", {}) or {}
        if getattr(job, "display_name", "") != PIPELINE_NAME:
            continue
        if not (has_project_labels(job) or labels.get(PIPELINE_BILLING_LABEL)):
            continue
        if state_name(job) not in PIPELINE_TERMINAL_STATES:
            continue
        plan.pipelines.append(job)
        pipeline_billing_ids.add(labels.get(PIPELINE_BILLING_LABEL, ""))
        detail = getattr(getattr(job, "_gca_resource", None), "job_detail", None)
        for attribute in ("pipeline_context", "pipeline_run_context"):
            context = getattr(detail, attribute, None) if detail else None
            context_name = getattr(context, "name", "") if context else ""
            if context_name:
                plan.metadata_contexts.add(context_name)
    for job in aiplatform.CustomJob.list(project=project, location=region):
        labels = getattr(job, "labels", {}) or {}
        if labels.get(PIPELINE_BILLING_LABEL) not in pipeline_billing_ids:
            continue
        if "vertex_pipelines" not in labels:
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
    for context_name in sorted(plan.metadata_contexts):
        print(f"Deleting metadata context: {context_name}")
        metadata_client.delete_context(name=context_name, force=True).result()
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
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--execute", action="store_true", help="delete after explicit confirmation")
    args = parser.parse_args()
    plan = collect_plan(args.project, args.region)
    print_plan(plan, args.project, args.region)
    if not args.execute:
        print("Simulation only. Re-run with --execute to delete after review.")
        return 0
    if input("Type DELETE to confirm: ") != "DELETE":
        print("Cleanup cancelled.")
        return 0
    delete_plan(plan, args.project, args.region)
    return 0


if __name__ == "__main__":
    sys.exit(main())
