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
