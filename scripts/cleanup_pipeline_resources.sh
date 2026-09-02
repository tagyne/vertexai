#!/usr/bin/env bash
set -euo pipefail

usage() { echo "Usage: $0 --project PROJECT --region REGION [--execute]" >&2; exit 2; }
project=""
region=""
execute="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) project="${2:-}"; shift 2 ;;
    --region) region="${2:-}"; shift 2 ;;
    --execute) execute="true"; shift ;;
    *) usage ;;
  esac
done
[[ -n "$project" && -n "$region" ]] || usage

echo "Pipeline-owned cleanup targets in project=${project}, region=${region}:"
echo "- completed Vertex AI pipeline jobs and custom jobs"
echo "- model resources carrying all MVP labels"
echo "- temporary objects under gs://<ML bucket>/pipeline-tmp/"
echo "Protected: Terraform backend, ML bucket, service account, IAM, stable endpoint."
[[ "$execute" == "true" ]] || { echo "Simulation only. Re-run with --execute to delete after review."; exit 0; }
read -r -p "Type DELETE to confirm: " confirmation
[[ "$confirmation" == "DELETE" ]] || { echo "Cleanup cancelled."; exit 0; }

gcloud ai pipeline-jobs list --project "$project" --region "$region" \
  --filter='state=(PIPELINE_STATE_SUCCEEDED OR PIPELINE_STATE_FAILED OR PIPELINE_STATE_CANCELLED)' \
  --format='value(name)' | while read -r job; do
    [[ -n "$job" ]] && gcloud ai pipeline-jobs delete "$job" --project "$project" --region "$region" --quiet
  done
gcloud ai models list --project "$project" --region "$region" \
  --filter='labels.project=student-performance-mlops AND labels.managed_by=vertex-pipeline AND labels.environment=dev' \
  --format='value(name)' | while read -r model; do
    [[ -n "$model" ]] && gcloud ai models delete "$model" --project "$project" --region "$region" --quiet
  done
while read -r bucket; do
  [[ -n "$bucket" ]] && gcloud storage rm --recursive "gs://${bucket}/pipeline-tmp/"
done < <(gcloud storage buckets list --project "$project" \
  --filter='labels.project=student-performance-mlops AND labels.managed_by=vertex-pipeline AND labels.environment=dev' \
  --format='value(name)')
echo "Dynamic pipeline jobs, labeled models, and temporary artifacts removed. No Terraform-owned resource was targeted."
