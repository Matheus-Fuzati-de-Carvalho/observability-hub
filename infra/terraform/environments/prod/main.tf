module "backend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "backend"
  image        = var.backend_image

  # Ambiente de prod: protege o serviço contra destroy acidental.
  deletion_protection   = true
  allow_unauthenticated = true
}
