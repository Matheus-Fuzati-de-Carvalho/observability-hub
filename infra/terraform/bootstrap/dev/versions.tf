terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Backend local intencional: o bootstrap cria o próprio bucket de state
  # remoto, então ainda não existe onde guardar seu state remotamente.
  # Este terraform.tfstate local é a única cópia — não apagar/versionar
  # fora do controle de quem administra a infra.
}

provider "google" {
  project = var.project_id
  region  = var.region
}
