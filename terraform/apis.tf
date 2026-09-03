locals {
  required_apis = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ])
  labels = {
    project     = "student-performance-mlops"
    managed_by  = "vertex-pipeline"
    environment = "dev"
  }
}

resource "google_project_service" "required" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
