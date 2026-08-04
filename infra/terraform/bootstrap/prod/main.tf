module "bootstrap" {
  source = "../modules/wif-bootstrap"

  project_id        = var.project_id
  environment       = "prod"
  region            = var.region
  github_repository = var.github_repository

  # Só workflows rodando na branch main podem assumir esta identidade,
  # espelhando a política "merge em main -> deploy em prod" definida no
  # CLAUDE.md. Isso é reforçado no próprio provider OIDC (main.tf do
  # módulo), não apenas na lógica do workflow.
  restrict_provider_to_ref = "refs/heads/main"
}
