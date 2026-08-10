module "backend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "backend"
  image        = var.backend_image

  # Ambiente de prod: protege o serviço contra destroy acidental.
  deletion_protection   = true
  allow_unauthenticated = true

  # Libera CORS pras duas URLs válidas do frontend em prod — todo Cloud Run
  # responde tanto na URL canônica (com hash) quanto na URL legada baseada
  # no número do projeto, e o browser pode acessar por qualquer uma das duas.
  env = {
    OBSERVABILITY_HUB_CORS_ORIGINS = "${module.frontend_cloud_run.service_url},${module.frontend_cloud_run.service_url_alt}"
  }
}

module "frontend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "frontend"
  image        = var.frontend_image

  # Frontend estático (serve -s dist) não tem endpoint /health — a raiz
  # responde 200 e serve pros probes de startup/liveness.
  health_check_path = "/"

  # Reaproveita o repositório Artifact Registry criado pelo backend_cloud_run
  # neste mesmo projeto, em vez de tentar criar um segundo "apps".
  manage_artifact_registry = false

  # Ambiente de prod: protege o serviço contra destroy acidental.
  deletion_protection   = true
  allow_unauthenticated = true
}
