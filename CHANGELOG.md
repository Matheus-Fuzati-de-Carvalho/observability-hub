# CHANGELOG — Observability Hub

Histórico de fases, decisões, erros cometidos e pivotagens.
Atualizado ao final de cada fase pelo Claude Code.

---

## Fase 1 — Infraestrutura base (concluída)

### O que foi feito
- Bootstrap do Terraform aplicado manualmente em dev e prod
  - Bucket GCS de remote state por ambiente
  - Workload Identity Federation (GitHub Actions → GCP sem service account keys)
  - Service accounts de deploy com permissões mínimas
- GitHub Actions configurados (5 workflows)
  - `terraform-plan.yml` — roda em todo PR que toca infra/
  - `terraform-apply-dev.yml` — push em qualquer branch exceto main
  - `terraform-apply-prod.yml` — push/merge em main
  - `backend-deploy-dev.yml` — build + push + deploy Cloud Run dev
  - `backend-deploy-prod.yml` — build + push + deploy Cloud Run prod
- Módulo Terraform `cloud-run` criado e aplicado em dev e prod
  - Artifact Registry repository
  - Service account de runtime dedicada (backend-run)
  - Cloud Run com health check em /health e lifecycle.ignore_changes na imagem
- Backend skeleton deployado em dev e prod
  - FastAPI com GET /health → {"status": "ok"}
  - Dockerfile multi-stage, usuário não-root, uv como gerenciador de pacotes

### Erros cometidos e aprendizados

**Erro 1 — Permissão faltando no bootstrap**
- O que aconteceu: `gh-deploy-prod` não tinha `roles/iam.serviceAccountAdmin`,
  apenas `roles/iam.serviceAccountUser`. O Terraform Apply falhou ao tentar
  criar a service account `backend-run` no primeiro deploy.
- Correção: adicionado `roles/iam.serviceAccountAdmin` no módulo wif-bootstrap
  e reaplicado o bootstrap manualmente em dev e prod.
- Aprendizado: ao definir permissões de deploy no bootstrap, sempre listar todos
  os tipos de recursos que o Terraform vai criar (SAs, buckets, Cloud Run, etc.)
  e garantir as roles correspondentes.

**Erro 2 — Corrida entre workflows (race condition)**
- O que aconteceu: `backend-deploy-prod.yml` e `terraform-apply-prod.yml`
  dispararam em paralelo no mesmo push. O deploy rodou antes do Terraform criar
  a infraestrutura, gerando drift — Cloud Run criado fora do state com SA default
  do Compute Engine em vez da `backend-run`.
- Correção: adicionado `needs: [wait-for-terraform]` no `backend-deploy-prod.yml`
  para garantir que o Terraform Apply conclua antes do deploy.
- Aprendizado: em monorepos onde um push pode tocar infra/ e apps/ juntos,
  sempre definir ordem explícita entre workflows de infra e de deploy.

**Erro 3 — Drift em prod após race condition**
- O que aconteceu: o Cloud Run criado com drift precisou ser apagado e recriado
  pelo Terraform. O `terraform apply` em environments/prod foi rodado manualmente
  para reconciliar o state.
- Correção: `gcloud run services delete` seguido de `terraform apply` local com
  credenciais de admin.
- Aprendizado: em ambientes sem tráfego real, apagar e recriar é mais seguro
  que `terraform import`. Com tráfego real, sempre preferir import.

### Mudanças de arquitetura
- Nenhuma mudança em relação ao planejado.

### Status final
- dev: Cloud Run ✅ | Artifact Registry ✅ | GET /health HTTP 200 ✅
- prod: Cloud Run ✅ | Artifact Registry ✅ | GET /health HTTP 200 ✅

---

## Fase 0 — Estrutura e documentação (concluída)

### O que foi feito
- Monorepo criado e pushado para GitHub
- Estrutura de pastas definida (apps/backend, apps/frontend, infra/terraform,
  docs/adr, scripts)
- CLAUDE.md criado com convenções completas do projeto
- .gitignore cobrindo Python/uv, Node/pnpm, Terraform, Docker e segredos
- PRD v1.0 criado com funcionalidades, MVP, métricas de sucesso e roadmap
- ADRs 001-005 criados documentando decisões de arquitetura:
  - ADR-001: Monorepo
  - ADR-002: GCP como cloud provider
  - ADR-003: Terraform com diretórios por ambiente
  - ADR-004: Workload Identity Federation
  - ADR-005: Stack minimalista (FastAPI + React + Cloud Run)

### Erros cometidos e aprendizados
- Nenhum erro técnico nesta fase.
- Aprendizado de processo: definir arquitetura e funcionalidades ANTES de abrir
  o Claude Code evita retrabalho. O CLAUDE.md com contexto completo é o
  investimento mais importante do projeto.

### Mudanças de arquitetura
- Nenhuma.

---

## Próximas fases

| Fase | Descrição | Status |
|---|---|---|
| Fase 1.5 | Dados mock no BigQuery (GA4 público) | ⏳ Pendente |
| Fase 2 | MVP: Catálogo + Volumetria + Freshness + Profiling | ⏳ Pendente |
| Fase 3 | Lineage, PII, Mapa de acesso | ⏳ Pendente |
| Fase 4 | FinOps completo | ⏳ Pendente |
