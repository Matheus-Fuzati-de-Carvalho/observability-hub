# CHANGELOG — Observability Hub

Histórico de fases, decisões, erros cometidos e pivotagens.
Atualizado ao final de cada fase pelo Claude Code.

---

## Fase 2 — Backend MVP (concluída)

### O que foi feito
- Domínio Catálogo (Fase 2A): 4 endpoints, `discover_regions()` para descoberta
  automática de região, modelo de acesso cross-project
- Domínio Freshness (Fase 2B): 2 endpoints, classificação de SLA por janelas
  fixas (12h/24h/48h/7d/1m)
- Domínio Profiling/quality (Fase 2C): 3 endpoints, `sql_builder.py` com
  geração dinâmica de SQL por coluna, dry run de custo, amostragem via
  `TABLESAMPLE SYSTEM`, drill-down de distribuição de nulos ao longo do tempo
- 155 testes unitários passando (100%), com mocks — nenhum toca o BigQuery real
- Validado com `curl` contra `observability-hub-dev` ao final de cada uma das
  três sub-fases, antes de cada commit

### Erros cometidos e aprendizados

**Erro 1 — `INFORMATION_SCHEMA.TABLE_PARTITIONS` não existe em multi-região**
- O que aconteceu: a query de tabelas do catálogo fazia `JOIN` com
  `TABLE_PARTITIONS` para obter `partition_column`; deu `404 NotFound` em
  datasets na multi-região `US`.
- Correção: `TABLE_PARTITIONS` nem tem um campo com o *nome* da coluna de
  particionamento (só `partition_id`, o valor da partição) — e não existe em
  `US`/`EU` de qualquer forma. `partition_column` passou a vir de
  `INFORMATION_SCHEMA.COLUMNS.is_partitioning_column`, que funciona em
  qualquer região e já estava sendo consultada para `clustering_columns`.
- Aprendizado: não confiar em nomes de campo documentados ou sugeridos sem
  validar contra o schema real (`SELECT * LIMIT 1` ou introspecção do
  `result().schema`).

**Erro 2 — `last_modified_time` incorreto, repetido em duas specs**
- O que aconteceu: a spec do catálogo referenciava
  `TABLES.last_modified_time` (não existe) e, na correção seguinte,
  `TABLE_STORAGE.last_modified_time` (também não existe). O mesmo erro
  apareceu de novo na spec de freshness, que também usa `TABLE_STORAGE`.
- Correção: `TABLES` não tem nenhum campo de "última alteração" nesta versão
  do BigQuery; o campo real em `TABLE_STORAGE` é `storage_last_modified_time`.
- Aprendizado: todo campo de `INFORMATION_SCHEMA` citado numa spec precisa
  ser confirmado contra o schema real do projeto antes de implementar — esse
  erro específico se repetiu em 3 ocasiões diferentes ao longo da Fase 2.

**Erro 3 — `description` não existe em `INFORMATION_SCHEMA.COLUMNS`**
- O que aconteceu: o endpoint de detalhe de tabela buscava `description`
  direto de `COLUMNS`; `400 Unrecognized name: description`.
- Correção: `description` vem de `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`,
  com `JOIN` em `field_path = column_name` para não duplicar linhas em
  colunas `STRUCT`/`RECORD` aninhadas.
- Aprendizado: mesmo aprendizado do Erro 2.

**Erro 4 — `TABLE_STORAGE` sem dados para as tabelas de `observability-hub-dev`**
- O que aconteceu: freshness e profiling dependem de `TABLE_STORAGE` para
  `last_modified_time`/`total_rows`/`size_bytes`; a view retornou 0 linhas
  para as tabelas do projeto dev durante toda a Fase 2.
- Investigação: `TABLE_STORAGE` exige a opção de projeto
  `enable_info_schema_storage` habilitada por região (via `ALTER PROJECT`) —
  mas essa opção já estava `true` em `observability-hub-dev` (confirmado
  consultando `INFORMATION_SCHEMA.PROJECT_OPTIONS`), então não era o
  bloqueio. O motivo real é o lag de propagação que a documentação do Google
  descreve como "cerca de 1 dia" após habilitar a opção ou após mudanças na
  tabela até os dados de storage aparecerem.
- Correção: todo campo que depende de `TABLE_STORAGE`
  (`last_modified_time`, `size_bytes`, `row_count`, `hours_since_update`,
  `sla_status`) foi tipado como opcional (`| None`) em vez de obrigatório.
- Aprendizado: qualquer domínio que dependa de `TABLE_STORAGE` precisa
  tolerar ausência de dado para tabelas recém-criadas ou recém-modificadas —
  não é bug do nosso código, é o comportamento documentado do BigQuery.

### Mudanças de arquitetura
- `resolve_dataset_region()` movido de `domains/catalog/repository.py` para
  `core/bigquery.py` durante a Fase 2B — passou a ser compartilhado entre
  catalog e freshness (e, na prática, também usado por quality na Fase 2C).
  `catalog/repository.py` reexporta o nome para não quebrar chamadas
  existentes de `service.py` e dos testes. Justificativa: `core/exceptions.py`
  já antecipava essa necessidade desde a Fase 2A ("catalog hoje; freshness e
  profiling depois").

### Status final
- Catálogo: 4 endpoints ✅ | Freshness: 2 endpoints ✅ | Profiling: 3 endpoints ✅
- 155 testes unitários, 100% passando ✅
- `ruff check` + `ruff format` limpos em todas as três sub-fases ✅
- Validado com `curl` contra `observability-hub-dev` (dados reais, incluindo
  multi-região `US`, tabelas particionadas/clusterizadas e profiling
  completo em `RAW.crm_leads`) ✅

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
| Fase 1.5 | Dados mock no BigQuery (GA4 público) | ✅ Concluída |
| Fase 2 | MVP: Catálogo + Freshness + Profiling (backend) | ✅ Concluída |
| Fase 2D | Frontend MVP | 🔄 Em andamento |
| Fase 3 | Lineage, PII, Mapa de acesso | ⏳ Pendente |
| Fase 4 | FinOps completo | ⏳ Pendente |
