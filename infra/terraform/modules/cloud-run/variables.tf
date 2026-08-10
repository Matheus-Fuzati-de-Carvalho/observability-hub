variable "project_id" {
  description = "ID do projeto GCP onde o serviço é criado."
  type        = string
}

variable "region" {
  description = "Região do Cloud Run, do Artifact Registry e do service account."
  type        = string
}

variable "service_name" {
  description = "Nome do serviço Cloud Run e prefixo dos recursos relacionados (ex: \"backend\")."
  type        = string
}

variable "artifact_registry_repository_id" {
  description = "Nome do repositório Docker no Artifact Registry, compartilhado entre os serviços do projeto."
  type        = string
  default     = "apps"
}

variable "image" {
  description = "Imagem do container. Usa uma imagem placeholder pública no primeiro apply; os workflows de deploy atualizam a revisão via `gcloud run deploy --image`, sem passar por este módulo (ver lifecycle.ignore_changes abaixo)."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "container_port" {
  description = "Porta que o container escuta (Cloud Run injeta $PORT com este valor)."
  type        = number
  default     = 8080
}

variable "health_check_path" {
  description = "Path usado pelos probes de startup e liveness do Cloud Run."
  type        = string
  default     = "/health"
}

variable "cpu" {
  description = "CPU alocada ao container (formato Cloud Run, ex: \"1\")."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memória alocada ao container (formato Cloud Run, ex: \"512Mi\")."
  type        = string
  default     = "512Mi"
}

variable "min_instance_count" {
  description = "Número mínimo de instâncias (0 permite scale-to-zero)."
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Número máximo de instâncias."
  type        = number
  default     = 2
}

variable "allow_unauthenticated" {
  description = "Se true, concede roles/run.invoker a allUsers. Hoje o serviço só expõe /health, sem dados sensíveis; revisitar quando entrar autenticação real de usuário."
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "Se true, bloqueia `terraform destroy` deste serviço Cloud Run."
  type        = bool
  default     = false
}

variable "manage_artifact_registry" {
  description = "Se true, este módulo cria e gerencia o repositório Artifact Registry. Deixe false em instâncias adicionais do módulo no mesmo projeto que reaproveitam um repositório já criado por outra instância (ex: frontend reaproveitando o repo criado pelo backend)."
  type        = bool
  default     = true
}

variable "env" {
  description = "Variáveis de ambiente injetadas no container em runtime."
  type        = map(string)
  default     = {}
}
