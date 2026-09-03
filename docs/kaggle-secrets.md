# Kaggle secrets

Terraform creates the Secret Manager containers `kaggle-username` and
`kaggle-key` and grants access only to the Vertex AI pipeline service account.
Terraform does not create secret versions and no Kaggle credential belongs in
the repository or in `terraform.tfvars`.

After `terraform apply`, add the values from a local shell. Do not put them in
the command history or a committed file:

```bash
printf '%s' "$KAGGLE_USERNAME" | gcloud secrets versions add kaggle-username \
  --data-file=- --project "$GOOGLE_CLOUD_PROJECT"
printf '%s' "$KAGGLE_KEY" | gcloud secrets versions add kaggle-key \
  --data-file=- --project "$GOOGLE_CLOUD_PROJECT"
```

The `download_dataset` pipeline component reads the latest versions and sets
`KAGGLE_USERNAME` and `KAGGLE_KEY` only in its process before calling
`kagglehub.dataset_download`.
