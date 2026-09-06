# Repository Guidelines

## Project Structure

- `src/` contains the KFP pipeline, training, prediction, submission, and monitoring code.
- `tests/` contains the pytest suite, including inference-contract and pipeline tests.
- `terraform/` provisions GCP APIs, storage, IAM, Vertex AI endpoints, Pub/Sub, and the monitoring Cloud Function.
- `functions/` contains deployable Cloud Functions; `monitoring/` contains the Vertex AI analysis schema.
- `docs/` documents architecture, deployment, prediction, monitoring, secrets, and cleanup procedures.

## Build, Test, and Development Commands

Use Python 3.11 and `uv`:

```bash
uv sync                         # Install locked dependencies
uv run pytest -q                # Run the complete test suite
uv run python -m src.submit ... # Compile and submit a Vertex AI pipeline
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
terraform -chdir=terraform plan
```

Run `terraform apply` only when provisioning or changing the GCP environment is intentional. Compile the pipeline locally when changing `src/pipeline.py` and verify its task dependencies and caching behavior.

## Coding Style and Naming

Use four-space indentation, Python type hints, short docstrings, and `snake_case` for Python identifiers. Keep feature names and dataset columns consistent with the inference contract. Pin dependency versions in `pyproject.toml` and update `uv.lock` with `uv lock`. Use Terraform `snake_case` resource names and run `terraform fmt` for `.tf` changes.

## Testing Guidelines

Tests use pytest and live in `tests/test_*.py`. Never place test code, test fixtures, or test-only helpers in `src/`; keep them in `tests/` instead. Helpers used exclusively by tests belong in `tests/`, and unused application helpers should be removed rather than retained in `src/`. Add focused tests for new behavior, especially input validation, pipeline contracts, idempotency, and monitoring payloads. Prefer local fakes over calls to live GCP services; run `uv run pytest -q` before committing.

## Commits and Pull Requests

Use concise imperative Conventional Commit-style subjects, such as `feat: add monitoring alert workflow` or `fix: validate prediction input`. Keep commits focused. Pull requests should explain the behavior change, list validation commands, identify Terraform/GCP impact, and document any required configuration or migration. Never include credentials, service-account keys, or generated Terraform state.

## Security and Operations

Use ADC (`gcloud auth application-default login`) and Secret Manager for credentials. Review Terraform plans before applying. Monitoring alerts create `PENDING_APPROVAL` requests; do not add automatic retraining without explicitly revisiting the approval boundary and IAM permissions.
