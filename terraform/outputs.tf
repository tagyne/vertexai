output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "ml_bucket_uri" {
  value = "gs://${google_storage_bucket.ml.name}"
}

output "pipeline_service_account" {
  value = google_service_account.pipeline.email
}

output "endpoint_id" {
  value = google_vertex_ai_endpoint.stable.name
}

output "kaggle_username_secret_id" {
  value = google_secret_manager_secret.kaggle_username.secret_id
}

output "kaggle_key_secret_id" {
  value = google_secret_manager_secret.kaggle_key.secret_id
}

output "monitoring_notification_channel" {
  value = google_monitoring_notification_channel.monitoring_pubsub.name
}

output "monitoring_alert_topic" {
  value = google_pubsub_topic.monitoring_alerts.id
}

output "monitoring_baseline_uri" {
  value = "gs://${google_storage_bucket.ml.name}/monitoring/baselines/student-performance/latest/train.csv"
}

output "monitoring_schema_uri" {
  value = "gs://${google_storage_bucket.ml.name}/monitoring/schema/analysis-instance.yaml"
}
