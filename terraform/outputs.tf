output "ml_bucket_uri" {
  value = "gs://${google_storage_bucket.ml.name}"
}

output "pipeline_service_account" {
  value = google_service_account.pipeline.email
}

output "endpoint_id" {
  value = google_vertex_ai_endpoint.stable.name
}
