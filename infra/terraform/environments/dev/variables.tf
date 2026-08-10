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

variable "backend_image" {
  description = "Imagem do backend. Deixe o default (placeholder) no primeiro apply; os workflows de deploy atualizam a revisão depois via gcloud run deploy."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "frontend_image" {
  description = "Imagem do frontend. Deixe o default (placeholder) no primeiro apply; os workflows de deploy atualizam a revisão depois via gcloud run deploy."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}
