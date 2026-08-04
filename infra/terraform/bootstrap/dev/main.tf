module "bootstrap" {
  source = "../modules/wif-bootstrap"

  project_id        = var.project_id
  environment       = "dev"
  region            = var.region
  github_repository = var.github_repository

  # Sem restrição de ref: qualquer branch pode assumir esta identidade,
  # espelhando a política "push em qualquer branch -> deploy em dev"
  # definida no CLAUDE.md.
}
