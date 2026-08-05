output "service_url" {
  description = "URL pública do serviço Cloud Run."
  value       = google_cloud_run_v2_service.service.uri
}

output "service_name" {
  description = "Nome do serviço Cloud Run (usado por `gcloud run deploy` nos workflows)."
  value       = google_cloud_run_v2_service.service.name
}

output "runtime_service_account_email" {
  description = "E-mail do service account que o Cloud Run usa em runtime."
  value       = google_service_account.runtime.email
}

output "artifact_registry_repository_url" {
  description = "Prefixo do repositório Docker (<region>-docker.pkg.dev/<project>/<repo>), usado para montar a tag da imagem nos workflows."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.apps.repository_id}"
}
