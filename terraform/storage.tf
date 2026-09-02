resource "google_storage_bucket" "ml" {
  name                        = "student-performance-mlops-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
  labels                      = local.labels
  versioning { enabled = true }
  depends_on = [google_project_service.required]
}
