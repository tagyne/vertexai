resource "google_secret_manager_secret" "kaggle_username" {
  secret_id = "kaggle-username"
  project   = var.project_id
  labels    = local.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "kaggle_key" {
  secret_id = "kaggle-key"
  project   = var.project_id
  labels    = local.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "pipeline_kaggle_username_access" {
  secret_id = google_secret_manager_secret.kaggle_username.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_secret_manager_secret_iam_member" "pipeline_kaggle_key_access" {
  secret_id = google_secret_manager_secret.kaggle_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pipeline.email}"
}
