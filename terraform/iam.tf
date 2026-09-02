resource "google_service_account" "pipeline" {
  account_id   = "student-performance-pipeline"
  display_name = "Student performance Vertex AI pipeline"
  project      = var.project_id
}

resource "google_storage_bucket_iam_member" "pipeline_storage" {
  bucket = google_storage_bucket.ml.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}
