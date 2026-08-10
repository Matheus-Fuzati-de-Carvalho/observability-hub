output "service_url" {
  description = "URL pública do serviço Cloud Run."
  value       = google_cloud_run_v2_service.service.uri
}

output "service_url_alt" {
  description = "URL alternativa do Cloud Run baseada no número do projeto (<service>-<project_number>.<region>.run.app) — coexiste com service_url e serve a mesma revisão; precisa estar em qualquer allowlist de CORS que dependa da URL do serviço."
  value       = "https://${var.service_name}-${data.google_project.current.number}.${var.region}.run.app"
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
  description = "Prefixo do repositório Docker (<region>-docker.pkg.dev/<project>/<repo>), usado para montar a tag da imagem nos workflows. Montado a partir das variáveis (não do recurso), pra funcionar independente de qual instância do módulo gerencia o repositório."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository_id}"
}
