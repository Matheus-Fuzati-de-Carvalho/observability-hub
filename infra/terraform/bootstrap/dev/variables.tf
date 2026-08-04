variable "project_id" {
  description = "ID do projeto GCP de dev."
  type        = string
  default     = "observability-hub-dev"
}

variable "region" {
  description = "Região padrão dos recursos."
  type        = string
  default     = "us-central1"
}

variable "github_repository" {
  description = "Repositório GitHub autorizado a assumir a identidade (org/repo)."
  type        = string
  default     = "Matheus-Fuzati-de-Carvalho/observability-hub"
}
