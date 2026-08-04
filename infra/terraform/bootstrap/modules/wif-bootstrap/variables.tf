variable "project_id" {
  description = "ID do projeto GCP onde o bootstrap deste ambiente é aplicado."
  type        = string
}

variable "environment" {
  description = "Nome do ambiente (\"dev\" ou \"prod\"). Usado em nomes e descrições de recursos."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment deve ser \"dev\" ou \"prod\"."
  }
}

variable "region" {
  description = "Região padrão usada pelo bucket de state e demais recursos regionais."
  type        = string
  default     = "us-central1"
}

variable "github_repository" {
  description = "Repositório GitHub autorizado a assumir a identidade federada, no formato \"org/repo\"."
  type        = string
}

variable "restrict_provider_to_ref" {
  description = "Se definido (ex: \"refs/heads/main\"), só workflows rodando nesse ref do repositório podem se autenticar via este provider. Usado para restringir a identidade de prod à branch main."
  type        = string
  default     = null
}

variable "state_bucket_force_destroy" {
  description = "Permite apagar o bucket de state mesmo com objetos dentro. Deve ficar false em uso normal."
  type        = bool
  default     = false
}
