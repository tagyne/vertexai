# Student Performance MLOps MVP

This project trains a `RandomForestRegressor` on the Kaggle Student
Performance and Study Habits dataset and runs the workflow on Vertex AI.

## Quickstart

1. Create the separate Terraform state bucket manually, then edit
   `terraform/terraform.tfvars` from the example.
2. Authenticate with `gcloud auth application-default login`.
3. Run `terraform -chdir=terraform init`, `fmt -check`, `validate`, `plan`,
   and `apply`.
4. Run `uv python pin 3.11`, `uv sync`, then:

Add the Kaggle credentials to Secret Manager as described in
[Kaggle secrets](docs/kaggle-secrets.md), then launch the pipeline:

```bash
uv run pytest -q
uv run python -m src.submit --project "$GOOGLE_CLOUD_PROJECT" \
  --region "${VERTEX_REGION:-europe-west9}" \
  --pipeline-root "gs://<ML_BUCKET>/pipeline-root" \
  --endpoint-id "<ENDPOINT_ID>"
```

See [prediction-contract.md](docs/prediction-contract.md),
[architecture.md](docs/architecture.md), and [cleanup.md](docs/cleanup.md).
