resource "google_pubsub_topic" "monitoring_alerts" {
  name       = "student-performance-monitoring-alerts"
  project    = var.project_id
  depends_on = [google_project_service.required]
}

resource "google_monitoring_notification_channel" "monitoring_pubsub" {
  display_name = "Student performance monitoring alerts"
  project      = var.project_id
  type         = "pubsub"
  labels = {
    topic = google_pubsub_topic.monitoring_alerts.id
  }
  user_labels = local.labels
}

resource "google_project_service_identity" "monitoring_notification" {
  provider   = google-beta
  project    = var.project_id
  service    = "monitoring.googleapis.com"
  depends_on = [google_project_service.required]
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_bigquery_dataset" "model_monitoring_logs" {
  dataset_id = "model_monitoring"
  location   = var.region
  project    = var.project_id
  labels     = local.labels
}

resource "google_bigquery_dataset_iam_member" "vertex_ai_logging" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.model_monitoring_logs.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
}

resource "google_storage_bucket_object" "monitoring_schema" {
  bucket       = google_storage_bucket.ml.name
  name         = "monitoring/schema/analysis-instance.yaml"
  source       = "${path.module}/../monitoring/analysis-instance.yaml"
  content_type = "application/yaml"
}

resource "google_pubsub_topic_iam_member" "monitoring_publisher" {
  project    = var.project_id
  topic      = google_pubsub_topic.monitoring_alerts.name
  role       = "roles/pubsub.publisher"
  member     = google_project_service_identity.monitoring_notification.member
  depends_on = [google_project_service.required]
}
