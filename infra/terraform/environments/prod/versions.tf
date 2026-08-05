terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Nome do bucket vem do output `state_bucket_name` do bootstrap
  # (infra/terraform/bootstrap/prod). Ver bootstrap/README.md.
  backend "gcs" {
    bucket = "observability-hub-prod-tfstate"
    prefix = "environments/prod"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
