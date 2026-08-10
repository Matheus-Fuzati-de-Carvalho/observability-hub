data "google_project" "current" {
  project_id = var.project_id
}

resource "google_artifact_registry_repository" "apps" {
  count = var.manage_artifact_registry ? 1 : 0

  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repository_id
  format        = "DOCKER"
  description   = "Imagens Docker dos apps do Observability Hub (backend, frontend)."
}

# O recurso ganhou `count` para permitir instâncias do módulo que reaproveitam
# um repositório criado por outra instância (ex: frontend + backend no mesmo
# projeto). Este `moved` remapeia o endereço de state de instâncias já
# aplicadas (ex: backend em dev/prod) sem destruir/recriar o repositório real.
moved {
  from = google_artifact_registry_repository.apps
  to   = google_artifact_registry_repository.apps[0]
}

# Identidade runtime do Cloud Run — hoje sem papéis próprios, já que ainda
# não há lógica de domínio (BigQuery/Cloud Logging) para autorizar. Papéis
# específicos entram conforme os domínios forem implementados.
resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${var.service_name}-run"
  display_name = "Cloud Run runtime SA (${var.service_name})"
}

resource "google_cloud_run_v2_service" "service" {
  project             = var.project_id
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.deletion_protection

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      image = var.image

      ports {
        container_port = var.container_port
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }

      startup_probe {
        http_get {
          path = var.health_check_path
          port = var.container_port
        }
        period_seconds    = 5
        failure_threshold = 3
      }

      liveness_probe {
        http_get {
          path = var.health_check_path
          port = var.container_port
        }
        period_seconds = 15
      }
    }
  }

  # A imagem é atualizada pelos workflows de deploy via `gcloud run deploy
  # --image ...`, fora do Terraform. Sem isso, o próximo `terraform apply`
  # reverteria a revisão em produção para a imagem placeholder default.
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }

  depends_on = [google_artifact_registry_repository.apps]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count = var.allow_unauthenticated ? 1 : 0

  project  = google_cloud_run_v2_service.service.project
  location = google_cloud_run_v2_service.service.location
  name     = google_cloud_run_v2_service.service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
