module "backend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "backend"
  image        = var.backend_image

  # Ambiente de dev: sem proteção contra destroy, permite scale-to-zero.
  deletion_protection   = false
  allow_unauthenticated = true

  # Libera CORS pras duas URLs válidas do frontend em dev (canônica + legada
  # por número do projeto, ver environments/prod/main.tf), mantendo o Vite
  # dev server local (localhost:5173) funcionando contra o backend de dev.
  env = {
    OBSERVABILITY_HUB_CORS_ORIGINS = "${module.frontend_cloud_run.service_url},${module.frontend_cloud_run.service_url_alt},http://localhost:5173"
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

  # Ambiente de dev: sem proteção contra destroy, permite scale-to-zero.
  deletion_protection   = false
  allow_unauthenticated = true
}
