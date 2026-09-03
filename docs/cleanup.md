# Cleanup

Run the cleanup script in simulation mode first:

```bash
uv run python scripts/cleanup_pipeline_resources.py \
  --project "$GOOGLE_CLOUD_PROJECT" --region "${VERTEX_REGION:-europe-west9}"
```

Review the displayed targets, then add `--execute` and type `DELETE`. The
script requires both project and region, is safe to re-run, and never calls
Terraform or targets the backend bucket, service account, IAM, or the stable
endpoint. It removes completed pipeline/custom jobs, their metadata contexts,
labeled models, and objects under `pipeline-root/` and `pipeline-tmp/` in the
labeled ML bucket. Destroy durable infrastructure only with Terraform after
the dynamic cleanup is complete.
