terraform {
  backend "gcs" {
    bucket = "vertexai-tf-state-bucket"
    prefix = "terraform/state"
  }
}
