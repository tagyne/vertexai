data "archive_file" "retraining_request" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/retraining_request"
  excludes    = ["__pycache__"]
  output_path = "${path.root}/.terraform/retraining-request.zip"
}

resource "google_storage_bucket_object" "retraining_request_source" {
  bucket = google_storage_bucket.ml.name
  name   = "functions/retraining-request-${data.archive_file.retraining_request.output_md5}.zip"
  source = data.archive_file.retraining_request.output_path
}

resource "google_service_account" "retraining_request" {
  account_id   = "student-performance-retraining"
  display_name = "Student performance retraining approval handler"
  project      = var.project_id
}

data "google_client_openid_userinfo" "terraform_runner" {}

resource "google_service_account_iam_member" "retraining_request_act_as" {
  service_account_id = google_service_account.retraining_request.name
  role               = "roles/iam.serviceAccountUser"
  member             = "user:${data.google_client_openid_userinfo.terraform_runner.email}"
}

resource "google_service_account" "retraining_build" {
  account_id   = "student-perf-fn-build"
  display_name = "Student performance Cloud Functions build"
  project      = var.project_id
}

resource "google_service_account_iam_member" "retraining_build_act_as" {
  service_account_id = google_service_account.retraining_build.name
  role               = "roles/iam.serviceAccountUser"
  member             = "user:${data.google_client_openid_userinfo.terraform_runner.email}"
}

resource "google_project_iam_member" "retraining_build_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.retraining_build.email}"
}

resource "google_project_iam_member" "retraining_build_artifact_registry" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.retraining_build.email}"
}

resource "google_project_iam_member" "retraining_build_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.retraining_build.email}"
}

resource "google_storage_bucket_iam_member" "retraining_request_storage" {
  bucket = google_storage_bucket.ml.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.retraining_request.email}"
}

resource "google_project_iam_member" "retraining_request_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.retraining_request.email}"
}

resource "google_project_iam_member" "retraining_request_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.retraining_request.email}"
}

resource "google_cloudfunctions2_function" "retraining_request" {
  name        = "student-performance-retraining-request"
  location    = var.region
  project     = var.project_id
  description = "Persist Model Monitoring alerts for human retraining approval"

  build_config {
    runtime         = "python311"
    entry_point     = "handle_retraining_request"
    service_account = google_service_account.retraining_build.id
    source {
      storage_source {
        bucket = google_storage_bucket.ml.name
        object = google_storage_bucket_object.retraining_request_source.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.retraining_request.email
    environment_variables = {
      RETRAINING_REQUEST_BUCKET = google_storage_bucket.ml.name
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.monitoring_alerts.id
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = google_service_account.retraining_request.email
  }

  depends_on = [
    google_project_service.required,
    google_project_iam_member.retraining_build_artifact_registry,
    google_project_iam_member.retraining_build_logs,
    google_project_iam_member.retraining_build_storage,
    google_service_account_iam_member.retraining_build_act_as,
    google_service_account_iam_member.retraining_request_act_as,
    google_storage_bucket_iam_member.retraining_request_storage,
    google_project_iam_member.retraining_request_event_receiver,
    google_project_iam_member.retraining_request_invoker,
  ]
}
