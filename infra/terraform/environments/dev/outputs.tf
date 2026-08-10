output "backend_url" {
  value = module.backend_cloud_run.service_url
}

output "backend_service_name" {
  value = module.backend_cloud_run.service_name
}

output "backend_runtime_service_account_email" {
  value = module.backend_cloud_run.runtime_service_account_email
}

output "artifact_registry_repository_url" {
  value = module.backend_cloud_run.artifact_registry_repository_url
}

output "frontend_url" {
  value = module.frontend_cloud_run.service_url
}

output "frontend_service_name" {
  value = module.frontend_cloud_run.service_name
}

output "frontend_runtime_service_account_email" {
  value = module.frontend_cloud_run.runtime_service_account_email
}
