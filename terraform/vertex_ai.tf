resource "google_vertex_ai_endpoint" "stable" {
  name         = "student-performance-endpoint"
  display_name = "student-performance-endpoint"
  location     = var.region
  labels       = local.labels
  depends_on   = [google_project_service.required]
}
