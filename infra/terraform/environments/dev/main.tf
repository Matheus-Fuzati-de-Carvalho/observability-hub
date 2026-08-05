module "backend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "backend"
  image        = var.backend_image

  # Ambiente de dev: sem proteção contra destroy, permite scale-to-zero.
  deletion_protection   = false
  allow_unauthenticated = true
}
