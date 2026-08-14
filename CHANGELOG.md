# CHANGELOG — Observability Hub

Histórico de fases, decisões, erros cometidos e pivotagens.
Atualizado ao final de cada fase pelo Claude Code.

---

## Sprint 3.2 — Qualidade, Discovery e melhorias de UX em tabelas (em andamento)

Branch `feat/sprint-3.2`, a partir de `main` pós-PR #17. Sete itens
planejados; seis implementados e testados nesta sessão (o item de score
de qualidade foi implementado, validado e depois removido por completo a
pedido do usuário).

### O que foi feito
1. **Filtros e ordenação client-side**: busca por nome + filtro por tipo/
   status SLA + colunas ordenáveis, sem mudança de backend, em
   `AssetsTable` (catálogo), `TableFreshnessTable` (tabelas de um
   dataset) e `DatasetFreshnessTable` (datasets de um projeto, adicionado
   depois a pedido do usuário). Componente `SortableTableHead`
   compartilhado, promovido de um componente que só existia na busca.
2. **Score de qualidade por tabela — implementado e revertido**: média
   ponderada de completude/freshness/duplicatas/documentação (0-100),
   persistida em Firestore por profiling, badge na tabela de ativos.
   Validado em dev e então removido por completo por decisão do usuário.
3. **Histórico de qualidade**: cada profiling grava um snapshot em
   Firestore (máximo 30 runs por tabela); aba "Histórico" no modal com
   gráfico de linha (`recharts`), tabela de runs expansível por coluna e
   alerta de degradação (>10pp de queda de densidade vs. run anterior).
4. **Lineage e tabelas órfãs**: novo domínio a partir de audit logs de
   BigQuery (Cloud Logging) — upstream/downstream de uma tabela e lista
   de órfãs (sem consumidor conhecido). Limitação de visibilidade tratada
   com honestidade: resultado vazio vem com aviso explicando que pode ser
   falta de atividade OU audit logs desabilitados (indistinguível via
   API), em vez de afirmar uma certeza que a implementação não tem.
   **Evoluído na mesma sessão para v2** (spec `docs/specs/lineage.md`):
   upstream/downstream deixou de ser 1 hop direto e virou cadeia
   transitiva completa (ex: `daily_summary` ← `ga4_sessions` ←
   `ga4_events`), representada como grafo dirigido (BFS bidirecional em
   `domains/lineage/service.py`, `max_hops` configurável, padrão 8),
   atravessando projetos GCP quando necessário (nó vira "acesso negado"
   em vez de derrubar a requisição se a SA não tiver Logging no projeto
   não-raiz). Frontend passou de duas listas planas para um diagrama
   (`LineageGraph.tsx`, `@xyflow/react` + `dagre` para layout), sempre
   com o prefixo `project.dataset.table`. Validado em dev pelo usuário
   após o deploy — cadeia completa (`ga4_events → ga4_sessions →
   daily_summary`) confirmada contra audit logs reais.
5. **Fingerprinting de PII**: novo domínio `domains/pii`, nova aba "PII"
   no mesmo modal de profiling (`ProfilingDialog.tsx`). Duas camadas:
   heurística de nome de coluna (grátis, `INFORMATION_SCHEMA.COLUMNS`) +
   amostragem real via `TABLESAMPLE SYSTEM` com `REGEXP_CONTAINS`/
   `COUNTIF` por coluna (email, CPF, CNPJ, telefone BR, CEP, cartão de
   crédito — conjunto BR completo, a pedido do usuário). Coluna só é
   sinalizada pela amostra se ≥ `match_threshold_pct` (padrão 5%) dos
   valores não-nulos amostrados baterem no regex, não "qualquer match" —
   reduz falso positivo de coincidência isolada. Mesmo padrão de
   `/estimate`+`/run` (dry-run antes de executar) e cache de 5min do
   domínio `quality`, reaproveitados ao máximo. Matching roda inteiramente
   em SQL dentro do BigQuery — a API nunca recebe nem loga um valor de
   coluna real, só contagens agregadas.

### Erros e decisões desta sessão

**Decisão 1 — Score de qualidade removido depois de validado**
- O usuário pediu a remoção completa (backend + frontend) do score de
  qualidade depois de já ter validado a feature em dev, sem registrar o
  motivo. Revertido preservando `core/sla.py` (extração de SLA
  compartilhada entre freshness e quality), que é uma refatoração válida
  independente do score — não fazia sentido desfazer só porque a feature
  que motivou a extração saiu.

**Decisão 2 — Lineage implementado mesmo com Data Access audit logs
desabilitados**
- Pré-requisito técnico da fonte de dados (audit logs de BigQuery via
  Cloud Logging) não está habilitado em nenhum ambiente. Decisão
  consciente do usuário: implementar a feature mesmo assim (ela funciona
  corretamente assim que os logs forem habilitados) em vez de bloquear a
  sprint esperando uma mudança de infraestrutura que não é código.
- Limite técnico registrado explicitamente: a API não consegue
  distinguir "sem atividade no período" de "audit logs desabilitados" —
  os dois casos retornam o mesmo resultado vazio. Resolvido com um campo
  de aviso explícito na resposta em vez de fingir certeza.
- O schema do payload dos audit logs (`BigQueryAuditMetadata`/
  `jobChange`) foi implementado a partir da documentação oficial do
  Google, sem poder validar contra um log real — vale revisitar assim
  que os audit logs forem habilitados e o primeiro job aparecer.

**Decisão 3 — Lineage v1→v2 sem endpoint novo, breaking change direto**
- A extensão pra cadeia transitiva trocou `LineageResponse` (upstream/
  downstream flat) por `LineageGraphResponse` (nodes/edges) na mesma
  rota, em vez de versionar a API. Único consumidor da v1 era
  `LineageTab.tsx` — sem clientes externos, sem convenção de
  versionamento de API em nenhum outro domínio do repo, então manter
  compatibilidade retroativa seria custo sem benefício real.
- Bug encontrado e corrigido no meio do caminho: a v1 comparava
  `(dataset_id, table_id)` descartando `project_id`, então uma tabela
  `outro-projeto.RAW.foo` podia colidir por engano com `RAW.foo` do
  projeto consultado. A travessia v2 casa sempre pela tripla completa.

**Decisão 4 — PII diverge do guard de view de quality: pula a query
paga inteiramente, não só o TABLESAMPLE**
- `quality` (profiling), quando a tabela é VIEW/MATERIALIZED VIEW, só
  omite a cláusula `TABLESAMPLE` e roda a query principal sem amostragem
  — aceitável porque profiling é a funcionalidade central do domínio.
  PII é uma checagem complementar; rodar sem amostragem escanearia a
  view inteira (que pode envolver uma query subjacente pesada) sem o
  usuário ter visto uma estimativa de custo antes. Decisão: pular a
  query de amostragem por completo pra view, mantendo só a heurística de
  nome (grátis) — mesmo padrão de dry-run/estimate de quality, mas com
  esse guard adicional.
- Limitação assumida conscientemente e documentada em
  `docs/specs/pii.md`: os padrões regex (CPF, CNPJ, telefone, cartão)
  validam só formato, sem dígito verificador nem algoritmo de Luhn — e
  não cobrem a variante sem formatação (dígitos crus), que teria alto
  risco de falso positivo contra qualquer sequência numérica do tamanho
  certo.

### Mudanças de arquitetura
- `core/sla.py`: classificação de SLA extraída de `domains/freshness`
  para `core/`, compartilhada com `domains/quality` (mesmo racional do
  `resolve_dataset_region()` na Fase 2B).
- `core/logging_client.py`: client compartilhado do Cloud Logging, mesmo
  padrão de `core/bigquery.py::get_client()` (singleton via `lru_cache`).
- `LoggingAccessDeniedError` (`core/exceptions.py`) + handler em
  `main.py`: mesmo padrão de `ProjectAccessDeniedError` — falta de IAM
  vira 403 com o comando `gcloud` de correção pronto na resposta.
- `@xyflow/react` + `dagre` (frontend): primeira lib de grafo/diagrama do
  projeto (antes só `recharts`, gráficos, não DAG), adicionada
  especificamente pro diagrama de lineage transitivo — nó custom
  (`LineageGraph.tsx`) reaproveita o padrão visual de bloqueado+tooltip
  já estabelecido nos botões de `AssetsTable.tsx` (item 1 desta sprint)
  pra representar tabelas em projeto sem acesso de Logging.
- `components/SqlPreview.tsx`: promovido de `features/quality/` pro
  nível compartilhado — componente já era genérico (`{sql, defaultOpen}`,
  sem lógica de domínio) e passou a ser usado por `quality` e `pii`, mesmo
  racional do `SortableTableHead` promovido no item 1.
- `domains/pii/`: `repository.py` duplica (não importa)
  `get_table_columns`/`is_view`/`dry_run` de `domains/quality/
  repository.py` — mesma decisão de isolamento de domínio já tomada em
  `domains/lineage/repository.py` (CLAUDE.md proíbe um domínio importar
  de outro).

### Status até o momento
- Backend: 337 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc -b`, `vite build` limpos (bundle cresceu
  para ~1.19 MB / gzip 364 kB)
- Validado em dev (`observability-hub-dev`) a cada item, pelo usuário,
  incluindo lineage v2 (cadeia transitiva confirmada contra audit logs
  reais). PII ainda não validado visualmente no momento deste registro —
  mesma limitação de lineage, depende de dado de teste com PII sintético
  em dev
- Ainda falta 1 de 7 itens (mapa de acesso) e nenhum PR foi aberto pra
  `main`

---

## Sprint 3.1 — Auth (Google OAuth) + UX pessoal (concluída, PR #17)

Reconstruída a partir da descrição do PR #17 — o SESSIONLOG não foi
atualizado durante aquela sessão (falha de processo corrigida a partir
desta sprint).

### O que foi feito
1. **Autenticação real**: senha hardcoded do frontend (dívida técnica
   registrada no backlog da Sprint 2) substituída por Google OAuth 2.0 —
   `domains/auth/` no backend (login, callback, sessão via JWT em cookie
   httpOnly de 12h, allowlist por domínio/email no Secret Manager);
   `RequireAuth` no frontend. Todos os routers de dados passaram a exigir
   sessão válida no backend, não só proteção de rota no frontend.
2. **Modal de profiling**: dois bugs de UI corrigidos (colapso de schema
   em dois níveis, scroll horizontal vazando dos controles) e refatorado
   para Tabs (Schema / Análise de qualidade).
3. **Favoritos**: domínio novo, Firestore por usuário, estrela na tabela
   de ativos com toggle otimista.
4. **Histórico de navegação**: domínio novo, duas subcoleções por usuário
   (visualizações de tabela / buscas), seção "Recentes" na sidebar.

### Erros e aprendizados
- Cookie de logout não limpava de fato a sessão (`delete_cookie` do
  Starlette precisa dos mesmos atributos do cookie original pra
  funcionar) — corrigido em fix separado, pós-validação.

### Status final
- 269 testes backend, `ruff`/`biome`/`tsc`/`vite build` limpos
- Validado em dev pelo usuário (login/logout, allowlist, favoritos,
  histórico, modal de profiling)

---

## Sprint 2.2 e 2.3 — Metadados de partição, refresh, busca reversa e UX (concluída)

Sete funcionalidades sobre o MVP de catálogo/freshness (Fase 2 backend +
Sprint 2 frontend, ambas já concluídas), todas na branch
`feature/partition-metadata`, testadas em dev e validadas pelo usuário
antes de qualquer PR para `main`.

### O que foi feito — Sprint 2.2

1. **Metadados de partição na tabela de ativos**: `partition_type`
   (`"event_date (DAY)"`), `min_partition`, `max_partition`,
   `partition_count` em `TableSummary`, buscados em paralelo só para
   tabelas particionadas.
2. **Botão "Ver partições"**: novo endpoint
   `GET .../tables/{table_id}/partitions`, modal com a lista completa de
   partições distintas + contagem de linhas.
3. **Botão de refresh**: `RefreshButton` compartilhado (`RotateCcw`,
   `animate-spin`), páginas de catálogo e freshness, refetch das queries
   TanStack Query da view atual sem navegar nem limpar o projeto
   selecionado.
4. **Busca reversa tabela → datasets**: novo endpoint
   `GET /catalog/{project_id}/search?q=&mode=exact|contains`, agrupando
   `datasets_with_match`/`datasets_without_match` (este último via
   detecção de prefixo/série, não lista todo dataset do projeto).

### O que foi feito — Sprint 2.3

5. Sidebar de datasets sem os indicadores de status SLA (bolinha
   colorida) — só nome + contagem de tabelas/views.
6. Projeto selecionado persistido em `localStorage`, restaurado e
   revalidado automaticamente no carregamento da página; limpa o storage
   e volta pro campo vazio se a revalidação falhar.
7. Terceiro mode de busca, `not_contains` — inverte a lógica (datasets
   onde nenhuma tabela contém o termo) reaproveitando `mode=contains` +
   o universo completo de datasets do projeto. Resultado da busca
   reescrito como tabelas ordenáveis/filtráveis client-side (`Dataset`,
   `Tabela`, `Atualizado em`, `Linhas`) — `row_count` precisou entrar no
   backend (`DatasetWithMatch`), reaproveitando a mesma chamada
   `client.get_table()` já feita para `last_modified_time`.

### Erros cometidos e aprendizados

**Erro 1 — Reversão completa da estratégia de partições logo na primeira
implementação**
- O que aconteceu: a primeira versão de `get_partition_stats()` seguiu a
  instrução original (usar `INFORMATION_SCHEMA.PARTITIONS`, metadado
  gratuito, com fallback N/D para datasets multi-região). Tecnicamente
  correta, mas **inútil na prática**: todos os datasets de dev e prod
  estão em `US`, então o resultado era N/D sempre. Um PR (#14) chegou a
  ser aberto com essa versão e foi fechado pelo usuário sem merge.
- Correção: reimplementada do zero como uma query real (`MIN`/`MAX`/
  `COUNT(DISTINCT)` direto na coluna de partição), com custo real de
  bytes escaneados em vez de metadado gratuito — mitigado com cache TTL
  de 5min por tabela.
- Aprendizado: "tecnicamente correto pela spec" não é o mesmo que "útil
  no ambiente real" — quando 100% dos dados de teste caem no caso
  degradado de uma spec (aqui, multi-região → N/D), vale checar contra o
  ambiente real antes de considerar a implementação pronta, não só
  contra a spec escrita. `INFORMATION_SCHEMA.PARTITIONS` continua sendo
  uma opção válida em datasets de região específica — só não serve como
  única fonte quando todo o ambiente observado é multi-região.

**Erro 2 — "Linhas" pedida numa tabela sem mudar backend**
- O que aconteceu: a spec da Sprint 2.3 pedia uma coluna "Linhas"
  ordenável no resultado da busca, mas também dizia explicitamente "sem
  mudança de backend" — e o endpoint de busca nunca retornou
  `row_count`. Contradição real, não resolvida com suposição.
- Correção: perguntado ao usuário antes de implementar; decidido
  adicionar `row_count` ao backend mesmo assim, reaproveitando a chamada
  `client.get_table()` que já buscava `last_modified_time` (sem query BQ
  extra).
- Aprendizado: quando uma instrução pede um dado que a fonte não tem E
  proíbe a única forma de obtê-lo, é um bloqueio real — vale perguntar
  em vez de escolher silenciosamente um dos dois lados.

### Mudanças de arquitetura
- Nenhuma mudança estrutural — todas as adições seguem os padrões já
  estabelecidos na Fase 2 (paralelismo com `ThreadPoolExecutor`, cache
  TTL em memória por processo, `service.py` orquestra e `repository.py`
  constrói SQL).

### Status final
- 219 testes unitários backend, 100% passando ✅
- `ruff check`/`ruff format`, `biome check`, `tsc -b`, `vite build`
  limpos em cada commit ✅
- Validado com `curl` contra `observability-hub-dev` (dados reais,
  incluindo o cenário GA4 completo de `not_contains`/prefixo) e pelo
  usuário na interface real, em cada uma das 7 funcionalidades ✅
- Renderização visual no browser **não verificada por este assistente**
  em nenhum momento — Chromium headless não roda neste sandbox (mesma
  limitação de sessões anteriores); toda validação visual foi feita
  pelo usuário diretamente em dev

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
| Fase 2D | Frontend MVP | ✅ Concluída |
| Sprint 2.2 | Metadados de partição, "Ver partições", refresh, busca reversa | ✅ Concluída |
| Sprint 2.3 | 4 melhorias de UX (sidebar, localStorage, not_contains, tabela ordenável) | ✅ Concluída |
| Sprint 3.1 | Auth (Google OAuth), favoritos, histórico, fixes no modal de profiling | ✅ Concluída |
| Sprint 3.2 | Filtros/ordenação, histórico de qualidade, lineage e órfãos, PII, mapa de acesso | ⏳ Em andamento (6 de 7 itens) |
| Fase 4 | FinOps completo | ⏳ Pendente |
