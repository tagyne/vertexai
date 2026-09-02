variable "project_id" {
  type        = string
  description = "GCP project hosting the MVP."
}

variable "region" {
  type    = string
  default = "europe-west9"
}
