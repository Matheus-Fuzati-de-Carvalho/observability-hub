locals {
  required_apis = [
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "storage.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
  ]

  # Papéis do SA de deploy: cobre exatamente os módulos já planejados em
  # infra/terraform/modules (cloud-run, artifact-registry, bigquery,
  # secret-manager, logging-sink) mais o necessário para o Cloud Run
  # deploy funcionar. Revisar/apertar conforme os módulos forem escritos.
  deployer_roles = [
    "roles/run.admin",
    "roles/artifactregistry.admin",
    "roles/bigquery.admin",
    "roles/secretmanager.admin",
    "roles/logging.configWriter",
    "roles/iam.serviceAccountUser",
    # Necessário para o módulo cloud-run criar a service account de runtime
    # do Cloud Run (ex: backend-run) via `terraform apply`. Faltava e causou
    # falha em produção (Error 403: iam.serviceAccounts.create denied).
    "roles/iam.serviceAccountAdmin",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "tfstate" {
  name                        = "${var.project_id}-tfstate"
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.state_bucket_force_destroy

  versioning {
    enabled = true
  }

  # Guarda contra "terraform destroy" acidental apagando o histórico de
  # state de todos os ambientes que apontam para este bucket.
  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions (${var.environment})"
  description               = "Federação de tokens OIDC do GitHub Actions para o ambiente ${var.environment}"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Obrigatório: sem attribute_condition, qualquer repositório do GitHub
  # (de qualquer conta) poderia tentar se passar por este pool. Quando
  # restrict_provider_to_ref é definido (prod), exige também o ref exato.
  attribute_condition = var.restrict_provider_to_ref == null ? (
    "assertion.repository == \"${var.github_repository}\""
    ) : (
    "assertion.repository == \"${var.github_repository}\" && assertion.ref == \"${var.restrict_provider_to_ref}\""
  )

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  project      = var.project_id
  account_id   = "gh-deploy-${var.environment}"
  display_name = "GitHub Actions deployer (${var.environment})"
  description  = "Identidade impersonada pelo GitHub Actions via Workload Identity Federation para terraform apply e deploy no ambiente ${var.environment}"
}

resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repository}"
}

resource "google_project_iam_member" "deployer_roles" {
  for_each = toset(local.deployer_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_storage_bucket_iam_member" "deployer_state_access" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.deployer.email}"
}
