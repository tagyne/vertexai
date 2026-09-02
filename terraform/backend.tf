terraform {
  backend "gcs" {
    bucket = "student-performance-mlops-tf-state"
    prefix = "terraform/state"
  }
}
