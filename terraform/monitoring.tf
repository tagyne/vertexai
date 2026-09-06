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
  member     = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-monitoring-notification.iam.gserviceaccount.com"
  depends_on = [google_project_service.required]
}

data "google_project" "current" {
  project_id = var.project_id
}
