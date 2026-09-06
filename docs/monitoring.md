# Monitoring and retraining approval

Terraform provisions the durable monitoring plumbing:

- a Pub/Sub topic for Model Monitoring alerts;
- a Cloud Monitoring Pub/Sub notification channel;
- a Cloud Functions 2nd gen handler;
- the service account and minimal GCS/Eventarc permissions;
- the Model Monitoring analysis schema.

The Vertex AI pipeline publishes the training split to the durable baseline
path, deploys the model, and creates or updates the monitoring job. The
monitoring job is deliberately not cached because it changes an external
resource.

## Provision the infrastructure

From the repository root:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform validate
terraform -chdir=terraform plan
terraform -chdir=terraform apply
```

Record the outputs:

```bash
terraform -chdir=terraform output monitoring_notification_channel
terraform -chdir=terraform output monitoring_baseline_uri
terraform -chdir=terraform output monitoring_schema_uri
```

## Run the training and monitoring pipeline

The notification channel output must be passed to the pipeline submission:

```bash
uv run python -m src.submit \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "${VERTEX_REGION:-europe-west9}" \
  --pipeline-root "gs://<ML_BUCKET>/pipeline-root" \
  --endpoint-id "<ENDPOINT_ID>" \
  --monitoring-notification-channel "<NOTIFICATION_CHANNEL_RESOURCE_NAME>"
```

The submission must use a pipeline root ending in `/pipeline-root`. The
baseline and schema URIs are derived from the same bucket and are written under
the durable `monitoring/` prefix.

## Approval flow

When Model Monitoring detects an anomaly, the notification channel publishes
an event to Pub/Sub. The Cloud Function writes the full alert to:

```text
gs://<ML_BUCKET>/monitoring/retraining-requests/<EVENT_ID>.json
```

The request has status `PENDING_APPROVAL`. An operator reviews the alert and
relaunches the pipeline manually if retraining is justified. The function uses
GCS generation preconditions, so Pub/Sub redelivery cannot create duplicate
requests.

This design intentionally does not grant the function permission to submit
Vertex AI pipeline jobs. It prevents drift alerts from causing retraining
loops or automatically promoting a model trained on anomalous data.
