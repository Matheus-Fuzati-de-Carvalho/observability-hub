output "state_bucket_name" {
  description = "Nome do bucket GCS de remote state deste ambiente."
  value       = google_storage_bucket.tfstate.name
}

output "workload_identity_provider" {
  description = "Nome completo do provider, usado em google-github-actions/auth (input workload_identity_provider)."
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "service_account_email" {
  description = "E-mail do service account que o GitHub Actions impersona, usado em google-github-actions/auth (input service_account)."
  value       = google_service_account.deployer.email
}
