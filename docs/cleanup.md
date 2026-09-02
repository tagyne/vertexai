# Cleanup

Run the cleanup script in simulation mode first:

```bash
bash scripts/cleanup_pipeline_resources.sh \
  --project "$GOOGLE_CLOUD_PROJECT" --region "${VERTEX_REGION:-europe-west9}"
```

Review the displayed targets, then add `--execute` and type `DELETE`. The
script requires both project and region, is safe to re-run, and never calls
Terraform or targets the backend bucket, ML bucket, service account, IAM, or
the stable endpoint. Destroy durable infrastructure only with Terraform after
the dynamic cleanup is complete.
