resource "google_vertex_ai_endpoint" "stable" {
  name         = "student-performance-endpoint"
  display_name = "student-performance-endpoint"
  location     = var.region
  labels       = local.labels
  predict_request_response_logging_config {
    enabled       = true
    sampling_rate = 1.0
    bigquery_destination {
      output_uri = "bq://${var.project_id}.${google_bigquery_dataset.model_monitoring_logs.dataset_id}.endpoint_logs"
    }
  }
  depends_on = [
    google_project_service.required,
    google_bigquery_dataset_iam_member.vertex_ai_logging,
  ]
}
