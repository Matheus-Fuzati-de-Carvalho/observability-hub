# SESSIONLOG — Observability Hub

Arquivo de continuidade de sessão. Atualizado pelo Claude Code antes de resets.
Lido obrigatoriamente no início de cada nova sessão após um reset.

---

## Status atual

**Última atualização:** 2026-08-13 — Sprint 3.2 em andamento (5 de 7 itens
concluídos e commitados; itens 4 e 5 aguardando validação do usuário em
dev). Sprint 3.1 (auth Google OAuth, favoritos, histórico, 4 fixes no
modal de profiling) foi concluída e mergeada em `main` via PR #17 antes
desta sessão — ver seção própria abaixo, reconstruída a partir do PR
porque o SESSIONLOG não foi atualizado naquela sessão.
**Fase atual:** Sprint 3.2 — Qualidade, Discovery e melhorias de UX em
tabelas (Fase 3 do CLAUDE.md, "Discovery"), branch `feat/sprint-3.2`
(a partir de `main` `44ad7c9`), commits `5516b36`..`28f1f7f`:

1. ✅ Filtros/ordenação — catálogo (`AssetsTable`) e freshness por tabela
   (`TableFreshnessTable`), depois estendido pra freshness por dataset
   (`DatasetFreshnessTable`)
2. ✅ Score de qualidade por tabela — implementado, validado em dev, e
   **removido por completo a pedido do usuário** (revert `59d4ae8`)
   antes de seguir pro item de histórico
3. ✅ Histórico de qualidade — aba "Histórico" no modal de profiling
   (`recharts`, alerta de degradação >10pp) — validado em dev
4. ✅ Lineage e tabelas órfãs — aba "Lineage" no modal + página "Tabelas
   órfãs" — **implementado e testado (302 testes, build limpo), ainda
   não validado visualmente em dev pelo usuário**
5. ⏳ Fingerprinting de PII — não iniciado
6. ⏳ Mapa de acesso — não iniciado

Ver seção "Sprint 3.2" abaixo para o detalhe de cada item (o número da
lista acima segue a ordem de execução real desta sessão, não
necessariamente a numeração original da spec).
**Próximo passo:** usuário está revalidando lineage/órfãs em dev depois do
fix de `c33f950` (bug de "Failed to fetch" ao olhar prod a partir de dev —
ver seção "Bug: lineage cross-project" abaixo) e do IAM cross-project de
`roles/logging.viewer` concedido nesta sessão. Depois da validação, seguir
pro item de PII — versão resumida da spec antes de implementar (preferência
já confirmada pelo usuário nesta sprint), sem spec formal em `docs/specs/`
ainda (fica pra documentação de encerramento da sprint, junto com lineage e
mapa de acesso). **Nenhum PR aberto** para `main` — aguardando os 7 itens
completos e validados, como pedido explicitamente no início da sprint.
`main`/prod seguem no PR #17 (`44ad7c9`), inalterados por esta sessão.
`docs/onboarding-cliente.md` (novo) e a seção "Registro de acessos e
configurações" do CLAUDE.md (nova) não fazem parte da spec da sprint —
foram um pedido à parte do usuário nesta sessão, já commitados/aplicados.

---

## Sprint 3.2 — Qualidade, Discovery e melhorias de UX (em andamento)

Branch `feat/sprint-3.2`, a partir de `main` (`44ad7c9`, pós-merge do PR
#17). Regras definidas pelo usuário no início da sprint: pytest depois de
cada domínio de backend, testar em dev depois de cada item, commitar na
branch (push só com aprovação explícita a cada vez), sem PR pra `main`
até os itens completos e validados, plano apresentado antes de qualquer
arquivo novo.

### Filtros e ordenação (commits `5516b36`, `dae151e`)
`AssetsTable` (catálogo) e `TableFreshnessTable` (freshness por tabela,
dentro de um dataset) ganharam busca por nome + filtro por tipo/status
SLA + colunas ordenáveis client-side (`useMemo`, sem mudança de
backend). Componente `SearchSortableHead` (já existia só na busca) foi
promovido pra `components/SortableTableHead.tsx` compartilhado. Descobriu-
se nessa hora que `DatasetFreshnessTable` (a tabela de *datasets*, na
raiz de `/freshness` — diferente de `TableFreshnessTable`) já existia sem
filtro nenhum; ganhou o mesmo tratamento depois, a pedido do usuário.

### Score de qualidade — implementado e depois removido (commits `695f9e1`,
`3b12689`, revert `59d4ae8`)
Implementado por completo: `core/sla.py` (SLA extraído de `freshness` pra
ser compartilhado com `quality`), `domains/quality/score.py` (média
ponderada — completude 40%, freshness 30%, duplicatas 20%, documentação
10%, valor neutro 50 nas três primeiras quando não há dado), persistência
do último profiling em Firestore (`profiling_results/
{project}_{dataset}_{table}`, coleção compartilhada — decisão consciente
pra não depender de quem rodou o profiling), endpoint `GET /api/v1/
quality/score/...`, badge colorido + tooltip com breakdown na
`AssetsTable`. **Validado em dev pelo usuário** — e então removido por
completo (revert manual preservando `core/sla.py`, que é refatoração
independente do score) a pedido explícito do usuário. `profiling_results`
não é mais escrito por nenhum código a partir deste commit; pode haver
documentos órfãos remanescentes no Firestore de dev de quando a feature
esteve ativa (ver "Backlog").

### Histórico de qualidade (commits `89796d2`, `6efeaa2`)
Cada profiling grava um snapshot em `profiling_history/
{project}_{dataset}_{table}/runs/{auto-id}` (Firestore, coleção
compartilhada, máximo 30 runs por tabela — mesmo padrão de trim-to-max de
`domains/history`, adaptado pra subcoleção em vez de coleção plana).
Endpoint `GET /api/v1/quality/history/...`. `run_profiling()` recuperou
os parâmetros `firestore_client`/`executed_by` que tinham sido removidos
no revert do score (agora servem o histórico). Frontend: aba "Histórico"
no modal de profiling — gráfico de linha (`recharts`, dependência nova)
com densidade ao longo do tempo, tabela de runs com linha expansível
mostrando completude por coluna, alerta quando a densidade cai mais de 10
pontos percentuais em relação ao run anterior. `useRunProfiling` invalida
a query de histórico ao concluir um run, pra aba atualizar sem fechar o
modal. **Validado em dev pelo usuário.**

### Lineage e tabelas órfãs (commits `12d6d9b`, `28f1f7f`)
Novo `domains/lineage/`, fonte de dados são audit logs de job completado
do BigQuery via Cloud Logging (formato `BigQueryAuditMetadata`/
`jobChange`, documentado em docs.cloud.google.com/bigquery/docs/reference/
auditlogs/migration — **schema do payload ainda não validado contra logs
reais** porque os Data Access audit logs continuam desabilitados em dev e
prod, ver "Backlog"). `referencedTables`/`destinationTable` de cada job na
janela de 30 dias reconstroem upstream/downstream de uma tabela e a lista
de órfãs de um projeto (tabela sem nenhum job que a referencie como
leitura). Limitação registrada explicitamente na API: não dá pra
distinguir "sem atividade" de "audit logs desabilitados" só pelo
resultado — quando vem vazio, a resposta inclui um campo `warning` com
instruções em vez de afirmar uma certeza que a implementação não tem.
Falta de `roles/logging.viewer` vira `LoggingAccessDeniedError` → 403 com
o comando `gcloud` pronto (mesmo padrão de `ProjectAccessDeniedError`).

Endpoints: `GET /api/v1/lineage/{project}/{dataset}/{table}` e
`GET /api/v1/lineage/{project}/orphans`. Frontend: aba "Lineage" no modal
de profiling, página "Tabelas órfãs" (rota `/orphans`, link na sidebar),
novo `components/ApiErrorNotice.tsx` compartilhado que mostra os comandos
de `error.body.fix` quando presentes — corrigiu de quebra o tipo de
`ApiErrorBody.fix` (já era array em runtime, estava tipado como
`string`). **Ainda não validado visualmente em dev pelo usuário** — só
testado via suíte de testes (23 novos) e build limpo. Como os audit logs
estão desabilitados, o comportamento esperado em dev agora é: aviso
amarelo em toda consulta, e a página de órfãs listando todas as tabelas
do projeto (esperado dada a limitação de visibilidade, não é bug).

### Bug: lineage cross-project dava "Failed to fetch" (commit `c33f950`,
sessão de 2026-08-14 depois de `d9401d2`)
Usuário validou lineage/órfãs em dev (projeto nativo, ok) mas achou "Failed
to fetch" ao trocar pra olhar o projeto prod com o Hub rodando em dev.
Causa raiz, confirmada nos logs reais do Cloud Run de dev
(`gcloud logging read ... severity>=ERROR`): `domains/lineage/repository.py`
capturava `google.api_core.exceptions.PermissionDenied` (classe de erro
gRPC), mas o client do Cloud Logging usa transporte REST
(`_use_grpc=False`, ver docstring de `core/logging_client.py`) — um 403 via
REST levanta `Forbidden`, não `PermissionDenied`. A exceção real escapava
sem tratamento, virava 500 não capturado por nenhum `@app.exception_handler`,
e por estar fora do `CORSMiddleware` nesse caminho o browser reportava
"Failed to fetch" em vez do 403 tratado que `LoggingAccessDeniedError` já
sabia gerar. Resto do backend já usava a classe certa (`core/bigquery.py`,
`domains/quality/repository.py`); só lineage tinha o import errado.
Corrigido trocando `PermissionDenied` por `Forbidden` no import e no
`except`; testes do módulo (que mockavam `PermissionDenied`, mascarando o
bug) corrigidos pra mockar `Forbidden`. 303 testes passando, ruff limpo.

Enquanto investigava, descobri que `roles/logging.viewer` (self) e os
Data Access audit logs do BigQuery já estavam habilitados nos dois
projetos desde antes desta sessão, sem nunca terem sido documentados aqui
— ver correção dos itens 8/9/10 do Backlog. A pedido do usuário, concedi
(ele rodou via `!`) `roles/logging.viewer` cross-project nos dois sentidos
(dev→prod e prod→dev) — mesmo padrão das roles de BigQuery já cross-granted
desde a Sprint 2. Confirmado ao vivo via `gcloud projects get-iam-policy`
depois do comando.

### Bug 2: lineage cross-project não estourava mais erro, mas retornava
sempre vazio (`roles/logging.privateLogViewer` faltando, mesma sessão)
Usuário revalidou depois do fix acima — "Failed to fetch" resolvido, mas
a mensagem virou o aviso estático de "nenhum evento encontrado nos audit
logs" pra `observability-hub-prod`, apesar de `auditConfigs` já estarem
habilitados (confirmado no Bug 1 acima). Suspeita inicial (dado
insuficiente/quantidade de eventos) descartada rodando a query real via
`gcloud logging read` como usuário: **11.298 entradas** de
`jobservice.jobcompleted` em prod nos últimos 30 dias, muito longe de
"sem atividade". Reproduzindo `repository.list_job_events` localmente com
essas credenciais (usuário, não a SA), os 11.298 eventos parseavam sem
problema — ou seja, o parser está correto, o bug é puramente de IAM.

Causa raiz, confirmada contra a documentação oficial do GCP
(`docs.cloud.google.com/logging/docs/access-control`): **Data Access
audit logs exigem `roles/logging.privateLogViewer` pra serem visíveis via
API, além de `roles/logging.viewer`** — Admin Activity/System Event/Policy
Denied logs bastam com `logging.viewer`, mas Data Access (categoria onde
vive o `jobCompletedEvent` que lineage lê) é mais restrita por design
(pode conter informação sensível sobre o que foi acessado). Sem
`privateLogViewer`, a chamada **não falha** — só retorna sempre vazio,
indistinguível de "sem atividade real" ou "audit logs desabilitados" só
pelo resultado. `roles/logging.privateLogViewer` já existia self (cada SA
no próprio projeto, daí dev-olhando-dev sempre ter funcionado) mas nunca
tinha sido cross-granted — só `logging.viewer` foi cross-granted no Bug 1
acima, o que bastou pra não estourar 403 mas não bastou pra ver os dados.

Corrigido em três frentes:
1. `domains/lineage/service.py::_EMPTY_RESULT_WARNING` reescrito pra
   mencionar as duas roles como causa possível, não só "audit logs
   desabilitados" (que era a única hipótese sugerida antes, incompleta).
2. `main.py::handle_logging_access_denied` (o 403 de
   `LoggingAccessDeniedError`, que dispara quando falta `logging.viewer`
   por completo) passou a sugerir as duas roles de uma vez, mesmo padrão
   de `ProjectAccessDeniedError`.
3. `docs/onboarding-cliente.md` corrigido — a primeira versão do
   documento (escrita mais cedo nesta mesma sessão, antes deste bug
   aparecer) tinha marcado `logging.privateLogViewer` como "não usada
   pelo código, não replicar em onboarding"; agora faz parte do
   checklist oficial, com nota de correção explicando o erro.

Comandos de `roles/logging.privateLogViewer` cross-project (dev→prod e
prod→dev) fornecidos ao usuário nesta sessão — **pendente confirmação de
execução e revalidação em dev**, ver `docs/onboarding-cliente.md` pra o
comando exato e o registro de quando for confirmado.

Nesta mesma sessão, criado `docs/onboarding-cliente.md` (checklist
completo de IAM/API/audit config pra um projeto cliente aceitar leitura do
Hub) e nova seção "Registro de acessos e configurações" no CLAUDE.md,
pedindo que toda concessão de acesso futura (IAM, API, audit config, em
qualquer projeto incluindo dev/prod um observando o outro) seja registrada
naquele documento no momento em que acontece — mitigação direta da falha
de processo que causou os itens 8/9/10 ficarem desatualizados.

### Status no fim desta sessão (commit `28f1f7f`)
- Backend: 302 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc -b`, `vite build` limpos (bundle
  929.60 kB / gzip 281 kB — cresceu bastante com `recharts`, ver
  "Backlog")
- Deploy automático em dev confirmado verde a cada push (`gh run list`)
  — branch `feat/sprint-3.2` no ar em `observability-hub-dev`
- `main`/prod inalterados desde o PR #17 (`44ad7c9`)

---

## Sprint 3.1 — Auth (Google OAuth) + UX pessoal (concluída, PR #17)

Sessão anterior a esta, reconstruída a partir da descrição do PR #17
(`gh pr view 17`) — o SESSIONLOG não foi atualizado entre o encerramento
da Sprint 2.2/2.3 e o início desta sessão (falha de processo já
sinalizada ao usuário nesta sessão).

- **Auth**: senha hardcoded (`AuthGate`, dívida técnica registrada no
  backlog da Sprint 2) removida por completo, substituída por Google
  OAuth 2.0 de verdade — `domains/auth/` (`/login`, `/callback`, `/me`,
  `/logout`), JWT de sessão de 12h em cookie `httpOnly; Secure;
  SameSite=None`, allowlist por domínio/email lida do Secret Manager.
  Todos os routers de dados (catalog, freshness, profiling, projects)
  passaram a exigir sessão válida no backend, não só proteção de rota no
  frontend. Dois fixes pós-validação: cookie de logout não limpava de
  verdade (`delete_cookie` do Starlette não replicava os atributos do
  cookie original), redirect pro `/login` não era imediato.
- **Modal de profiling**: bug de colapso do schema corrigido em dois
  níveis (colunas STRUCT/ARRAY colapsáveis individualmente + seção
  inteira), fix de scroll horizontal vazando dos controles pra fora do
  modal, refatorado pra Tabs (shadcn/ui) — "Schema" e "Análise de
  qualidade" como abas separadas.
- **Favoritos**: `domains/favorites/`, Firestore por usuário
  (`users/{email}/favorites/{doc_id}`, doc_id determinístico), estrela em
  cada linha de `AssetsTable` com toggle otimista, seção "Favoritos" na
  sidebar com navegação + highlight.
- **Histórico** (de navegação — diferente do "histórico de qualidade" da
  Sprint 3.2): `domains/history/`, duas subcoleções por usuário
  (`history_table_views`/`history_searches`, decisão pra evitar depender
  de índice composto não provisionado), seção "Recentes" na sidebar,
  dropdown de buscas recentes na tela de busca.
- 269 testes backend, `ruff`/`biome`/`tsc`/`vite build` limpos. Validado
  em dev pelo usuário (login/logout, allowlist, as 4 melhorias do modal,
  favoritos e histórico); renderização visual não verificada por este
  assistente em nenhum momento (mesma limitação de Chromium headless de
  sempre).

---

## Sprint 2.2 — Funcionalidade 1 (metadados de partição)

**Versão 1 (revertida pelo usuário):** `get_partition_stats()` consultava
`INFORMATION_SCHEMA.PARTITIONS` (dataset-qualified, metadado gratuito),
retornando N/D direto para datasets multi-região (US/EU) sem tentar a
query. Como todos os datasets de dev/prod estão em `US`, isso significava
N/D sempre — comportamento tecnicamente correto pra limitação do BQ, mas
inútil na prática. PR #14 foi aberto com essa versão e fechado pelo
usuário sem merge por estar incorreto.

**Versão 2 (atual):** `get_partition_stats()` roda uma query real e leve
(uma coluna só, sem filtro) direto na tabela:
```sql
SELECT MIN(`{campo}`) AS min_partition, MAX(`{campo}`) AS max_partition,
       COUNT(DISTINCT `{campo}`) AS partition_count
FROM `{project}.{dataset}.{tabela}`
```
Funciona em qualquer região (não depende de `INFORMATION_SCHEMA.
PARTITIONS`), mas tem custo real de bytes escaneados (ao contrário de
metadado do `INFORMATION_SCHEMA`) — por isso ganhou cache TTL de 5min por
tabela (`repository._partition_stats_cache`, mesmo padrão do
`get_table_cached` de `core/bigquery.py`, mas local ao domínio catalog).
`campo` vem de `partition_column` (já derivado de
`COLUMNS.is_partitioning_column`, funciona em qualquer região). Também
ganhou `partition_type` ("event_date (DAY)"), lido de
`bq_table.time_partitioning`/`range_partitioning` — já vinha no
`client.get_table()` cacheado que `get_tables_summary` já chamava pra
row_count/size/modified, sem chamada extra.

**Confirmado ao vivo em dev** (`observability-hub-dev`, branch
`feature/partition-metadata`, commit `ea31bd6`):

| Tabela | Partitioned | Tipo | Min | Max | Count |
|---|---|---|---|---|---|
| `RAW.events` | true | `event_date (DAY)` | `2021-01-01` | `2021-01-30` | `3` |
| `TRUSTED.ga4_events` | true | `event_date (DAY)` | `2021-01-01` | `2021-01-18` | `4` |
| `TRUSTED.sessions` | true | `session_date (DAY)` | `2021-01-06` | `2021-01-31` | `7` |
| `RAW.crm_leads` | false | — | — | — | — |

Valores reais (dados mock de dev estão em jan/2021), não N/D — objetivo da
correção alcançado. `RAW.crm_leads` (não particionada) corretamente sem
dados de partição.

**Não verificado visualmente:** renderização real da tabela no frontend —
Chromium headless não roda neste sandbox (limitação já registrada em
sessões anteriores, ver "Decisões e erros de sessões anteriores" #7).
Validado só via `tsc`/`vite build`/`biome check` limpos e a API real via
`curl`.

Além dos 3 campos, ganhou também `partition_type` na tabela de ativos e um
botão **"Ver partições"** (linhas particionadas) que abre um modal com a
lista completa de partições distintas + contagem de linhas — novo
endpoint `GET /api/v1/catalog/{project_id}/datasets/{dataset_id}/
tables/{table_id}/partitions` (`TableNotPartitionedError` → 400 pra tabela
não particionada). Testado ao vivo em `RAW.events`: 3 partições, ordem
decrescente, valores batendo com a query direta. Commit `a0696fb`.

---

## Sprint 2.2 — Funcionalidade 2 (botão de refresh)

Só frontend. `RefreshButton` (`src/components/RefreshButton.tsx`,
`RotateCcw` do lucide, `animate-spin` + `disabled` durante fetch) nos
headers de `CatalogDatasetPage` (refetch de tables/datasets/freshness — as
três alimentam a página) e `FreshnessPage` (refetch de freshness). Não
entrou em `CatalogOverviewPage` (placeholder sem dados, dataset ainda não
selecionado) nem no modal de profiling, como pedido. Commit `a4083fc`.
Validado pelo usuário em dev (comportamento visual — spin/disable/reload
— não pôde ser confirmado neste sandbox, ver limitação de Chromium
headless acima).

---

## Sprint 2.2 — Funcionalidade 3 (busca reversa tabela → datasets)

Novo endpoint `GET /api/v1/catalog/{project_id}/search?q=&mode=exact|
contains` — busca em `INFORMATION_SCHEMA.TABLES` de todas as regiões do
projeto em paralelo (`repository.search_tables`, mesma técnica de
`discover_regions`). Resultado agrupado em `datasets_with_match` (com
`last_modified_time` real via `client.get_table()`, reaproveitando
`core.bigquery.get_tables_metadata`) e `datasets_without_match`.

`datasets_without_match` **não** lista todo dataset do projeto sem a
tabela — só os que têm outra tabela da mesma série: prefixo derivado
removendo o sufixo numérico final de `q` (`repository.
derive_search_prefix`, ex: `"events_20260812"` → `"events_"`), buscado via
`GROUP BY` + `MAX(table_name)` por dataset. Sem sufixo numérico em `q`,
`datasets_without_match` fica vazio — não há "série" pra comparar.

Frontend: nova seção "Busca" na sidebar (ícone `Search`), campo + toggle
Exato/Contém (dois `Button`, sem novo componente shadcn), busca como
`useMutation` (não `useQuery` — é sob demanda, não reativa), mensagem de
loading, dois grupos de resultado (✅ encontrado / ❌ ausente com motivo) e
mensagem de vazio pra `contains` sem resultado. Commit `50526e9`.

**Confirmado ao vivo em dev** (`observability-hub-dev`) — importante: os
dados mock mudaram desde a spec original da Sprint 2.2 (que previa "RAW
como único dataset com match"). Dev agora tem 3 datasets
`analytics_100001/2/3`, cada um com tabelas `events_YYYYMMDD` sharded por
nome (cenário GA4 real, não só `RAW.events` particionado por coluna):

| Busca | Resultado |
|---|---|
| `q=events_20260812&mode=exact` | 3 matches (`analytics_100001/2/3`) |
| `q=events_20260813&mode=exact` (data ainda não carregada) | 0 matches, 3 `datasets_without_match` com `reason=prefix_exists` e `latest_partition=events_20260812` — cenário exato da spec |
| `q=crm&mode=contains` | 1 match (`RAW.crm_leads`) |
| `q=zzz_nao_existe&mode=contains` | Vazio, `200 OK` |

`RAW.events` nunca aparece nessas buscas — é uma tabela só, particionada
por coluna (`event_date`), não por nome sharded, então não bate com busca
por nome de tabela. Validado pelo usuário.

---

## Sprint 2.3 — 4 melhorias de UX (commit `2630fb9`)

Implementadas em um único commit (a Sprint 2.3, diferente da 2.2, não
pediu branch/commit por item — só documentação separada, ver abaixo).
Todas testadas em dev e validadas pelo usuário.

1. **Sidebar sem bolinhas de status SLA**: `DatasetSidebar.tsx` não busca
   mais `useProjectFreshness` nem renderiza `STATUS_DOT_COLOR` — só nome +
   contagem de tabelas/views. O backlog item "datasets só com views sem
   indicador de freshness na sidebar" (ver "Backlog" abaixo) fica
   obsoleto — não há mais indicador nenhum ali.

2. **Projeto persistido em localStorage**: `hooks/useLastProject.ts` já
   tinha `setLastProjectId` (escrita) mas nenhuma leitura — ganhou
   `getLastProjectId`/`clearLastProjectId`. `ProjectSelector.tsx` restaura
   e revalida automaticamente no mount; se a revalidação falhar, limpa o
   storage e volta pro campo vazio (só no caminho de restore automático —
   uma falha de validação manual, digitada pelo usuário, continua
   deixando o campo preenchido pra ele corrigir, comportamento inalterado
   nesse caso).

3. **Mode `not_contains` na busca**: `SearchMode` ganhou o terceiro valor.
   `service._search_not_contains` trata à parte — não é uma variação da
   query SQL de match dos outros modes, é uma pergunta invertida (usa
   `get_datasets_summary` pra saber todos os datasets do projeto e
   `search_tables(mode="contains")` pra saber quem tem match; a diferença
   vira o resultado). `datasets_with_match` fica sempre vazio nesse mode.

4. **Resultado da busca em tabela ordenável/filtrável**: dois componentes
   novos (`SearchMatchesTable`, `SearchAbsentTable`) com sort client-side
   por coluna e filtro de texto em Dataset/Tabela. A coluna "Linhas"
   pedida na spec não existia no backend (`GET /search` nunca retornou
   `row_count`) e a spec dizia "sem mudança de backend" — conflito real,
   perguntado ao usuário, que escolheu adicionar `row_count` ao backend
   (reaproveita a mesma chamada `client.get_table()` já feita pra
   `last_modified_time`, sem query BQ extra).

**Confirmado ao vivo em dev** (via `curl`, backend):
- `mode=not_contains&q=crm`: exclui corretamente `RAW` (único dataset com
  `crm_leads`), lista os outros 5 datasets com `reason=no_match`.
- `mode=exact&q=events_20260812`: `row_count: 1000` real em cada match.
- `GET /projects/.../validate` seguiu funcionando (regressão check pro
  fluxo de restore do item 2).

**Não verificado visualmente**: renderização real das 4 melhorias no
browser — mesma limitação de Chromium headless de sempre. Validação
visual de todas as 7 funcionalidades desta sessão (2.2 + 2.3) foi feita
pelo usuário, não por este assistente.

---

## Sprint 2.2/2.3 — Documentação

Atualizados nesta sessão, depois das 7 funcionalidades validadas em dev
(commit separado da Sprint 2.3, como pedido):
- `CHANGELOG.md`: nova seção "Sprint 2.2 e 2.3" com o que foi feito, os 2
  erros/aprendizados da sessão (reversão da estratégia de partições;
  conflito "Linhas sem mudar backend") e tabela de próximas fases
  atualizada (Fase 2D e Sprint 2.2/2.3 marcadas concluídas, Fase 3 como
  próxima).
- `docs/prd.md`: tabela de roadmap (seção 7) atualizada — Fase 1 e Fase 2
  estavam desatualizadas (marcadas "em andamento"/"pendente" mesmo já
  concluídas antes desta sessão).
- `docs/adr/ADR-008-terraform-plan-prod-removido.md`: novo ADR
  documentando por que `terraform-plan.yml` não tem job "Plan (prod)" —
  decisão já estava implementada (o workflow já tinha um comentário
  explicando) mas nunca formalizada em ADR. Contexto → decisão →
  alternativas → consequências, como as demais.
- `docs/specs/catalog.md` (v1.4 → v1.5): endpoints `/partitions` e
  `/search` documentados, incluindo a ressalva de que `get_partition_stats`
  não é mais metadado gratuito (é query real, ao contrário do resto da
  spec) — e por quê (`INFORMATION_SCHEMA.PARTITIONS` não serve como fonte
  única quando 100% do ambiente observado é multi-região).
- `docs/specs/profiling.md` (v1.1 → v1.2): suporte a views (omissão de
  `TABLESAMPLE`), schema preview no modal (STRUCT/ARRAY com badge
  "Complexo" mas visível no schema, mesmo sem métricas), e a tabela de
  tipo lógico inferido corrigida pra refletir a ordem real de checagem
  (tipo físico antes de heurísticas de cardinalidade — a ordem antiga era
  auto-contraditória).
- `SESSIONLOG.md`: este arquivo, nesta seção.

---

## O que foi feito na Sprint 2

A Sprint 2 cobriu do PR #2 ao #13 (o PR #1, deploy do frontend no Cloud Run,
já estava documentado no encerramento da sessão anterior). Trabalho spread
por várias sessões — o que segue é a reconstrução a partir do histórico real
de PRs (`gh pr list`/`gh pr view`), não só da sessão mais recente.

### Infra e correções de plataforma
- **PR #2 — CORS para a segunda URL do Cloud Run**: todo serviço Cloud Run
  responde em duas URLs válidas (a com hash e a legada por número de
  projeto); só a primeira estava na allowlist de CORS do backend, quebrando
  o frontend quando acessado pela URL de project number. Módulo `cloud-run`
  ganhou `output "service_url_alt"` (via `data "google_project"`,
  reaproveitável), e as duas URLs entraram em `OBSERVABILITY_HUB_CORS_ORIGINS`
  nos dois ambientes.
- **PR #10 / #11 — bumps de versão pra forçar redeploy em dev**: dev tinha
  ficado defasado de `main` (deploy automático só dispara em push que toca
  os paths do workflow, não em "está tudo commitado" — mesma armadilha já
  registrada na sessão anterior). Bump de versão em `package.json` (frontend)
  e `pyproject.toml`/`uv.lock` (backend) sincronizou dev com o código real.

### Domínio quality/profiling
- **PR #3 — 403 limpo em vez de 500 no profiling**: a runtime SA tinha
  `metadataViewer`+`jobUser` (suficiente pra catalog/freshness, só
  `INFORMATION_SCHEMA`), mas profiling roda SQL real contra dados de tabela
  e precisa de `bigquery.dataViewer` — faltava nos dois ambientes. As 4
  funções de query em `domains/quality/repository.py` passaram a capturar
  `Forbidden` e relançar `ProjectAccessDeniedError` (já mapeada pra 403 no
  handler). O handler em `main.py` também estava sugerindo só uma role no
  `fix`; passou a sugerir as três (idempotente, seguro rodar mesmo quando só
  uma faltava).
- **PR #4, #5, #6 — três rodadas até acertar o modal de profiling**: scroll
  (modal + área de SQL), depois largura/KPIs/SQL colapsável, depois a causa
  raiz real da largura: `DialogContent` do shadcn já vem com `sm:max-w-sm`
  embutido, e no CSS compilado pelo Tailwind v4 essa regra `sm:` aparece
  **depois** de qualquer `max-w-[...]` simples adicionado via `className` —
  vencia o empate de especificidade silenciosamente em qualquer tela
  ≥640px, apesar do build passar limpo nas duas tentativas anteriores.
  Resolvido com `w-[90vw]! max-w-[1000px]!` (sintaxe `!important` do
  Tailwind v4), confirmado inspecionando o CSS gerado.
- **PR #8 — profiling em views**: `TABLESAMPLE SYSTEM` não é suportado pelo
  BigQuery em VIEW/MATERIALIZED VIEW — causava "Failed to fetch". Query
  builder ganhou `is_view: bool` (omite `TABLESAMPLE`/`sample_percent`
  quando `True`), detectado via `INFORMATION_SCHEMA.TABLES`. Frontend
  desabilita o campo de amostragem com aviso quando a tabela é view. Mesmo
  PR separou a contagem de tabelas e views no catálogo (sidebar e KPI
  cards), que antes vinham somadas sob um único rótulo "tabelas".
- **PR #9 — schema da tabela no modal antes de rodar profiling**: nova
  `SchemaTable` (Nome/Tipo/Nullable) usando o endpoint de detalhe já
  existente, com parsing de subcampos STRUCT/ARRAY (badge "Complexo"),
  destaque pra colunas de data e badge de coluna de partição. Header do
  modal ganhou badges "Particionada por"/"Clusterizada por".
- **PR #7 — inferência de tipo lógico**: colunas numéricas (INTEGER,
  FLOAT64, NUMERIC, BIGNUMERIC, INT64) e de data/hora (DATE/DATETIME/
  TIMESTAMP) passaram a ter `inferred_logical_type` correto direto pelo tipo
  físico, sem cair nas heurísticas de cardinalidade (categorical/id) que
  valiam só quando o tipo físico não decidia sozinho.

### Domínio freshness
- Colunas de contagem por SLA na tabela de freshness (commit `8324fbe`,
  direto em `main`, sem PR associado).
- Backlog registrado (commit `ab68237`, também direto em `main`): datasets
  só com views não têm indicador de freshness na sidebar (sem
  `modified_time` de dados) — ainda pendente, ver "Backlog" abaixo.
- **Esta sessão (PR #12)**: `get_tables_summary` (catalog) e
  `get_table_freshness` (freshness) passaram de `INFORMATION_SCHEMA.
  TABLE_STORAGE` (lag de até 24h) para `client.get_table()` — tempo real,
  chamadas em paralelo (`ThreadPoolExecutor`) com cache TTL de 5min
  compartilhado (`core/bigquery.py`). Escopo decidido com o usuário: as
  visões agregadas por projeto (`get_datasets_summary`,
  `get_freshness_summary_by_dataset`) ficaram em `TABLE_STORAGE` de
  propósito, pra não virar uma chamada de API por tabela do projeto inteiro
  numa tela de dashboard. Specs `catalog.md` (v1.3) e `freshness.md` (v1.2)
  atualizadas.

### UX geral e autenticação
- **PR #7 — 5 melhorias de UX**: tabela de resultados sem scroll horizontal
  (truncamento com ellipsis em Min/Max), seletor de projeto migrado da tela
  `/` isolada pra `Topbar` (visível em qualquer página, `ProjectContext` +
  `ProjectSelector`, rotas perderam o prefixo `/p/:projectId`), e
  `AuthGate` — tela de login com senha hardcoded (`senha123`) e sessão em
  `sessionStorage`. Ver nota de dívida técnica no Backlog.
- **Esta sessão (PR #13)**: `GET /projects/{id}/validate` ganhou
  `is_native` (compara `project_id` com `client.project`, mesma fonte já
  usada no fix do 403). Badge na topbar — verde "Projeto nativo" / amarelo
  "Projeto externo" — com tooltip. Spec `catalog.md` bump pra v1.4.

### IAM cross-project (esta sessão, fora de qualquer PR — aplicado via `gcloud` direto)
O usuário rodou manualmente (com aprovação explícita a cada comando, via
`!`) bindings cruzados entre os dois projetos:
- `backend-run@observability-hub-prod` ganhou `metadataViewer` +
  `jobUser` + `dataViewer` em `observability-hub-dev`.
- `backend-run@observability-hub-dev` ganhou as mesmas três roles em
  `observability-hub-prod`.

Ambas as direções foram confirmadas como **intencionais** pelo usuário
depois de eu (assistant) sinalizar o trade-off de segurança: dev faz deploy
automático em qualquer push sem gate de revisão, então a SA de dev agora
consegue ler dados reais de prod (potencialmente com PII, dado o escopo do
produto) a partir de qualquer branch nova. Ver "Backlog" — considerar
revisitar se o risco incomodar mais adiante.

---

## Erros encontrados e resolvidos (Sprint 2)

- **500 em vez de 403 no profiling**: `Forbidden` do BigQuery vazando sem
  tratamento — corrigido capturando e relançando `ProjectAccessDeniedError`
  (PR #3).
- **CORS quebrando só na URL alternativa do Cloud Run**: cada serviço
  responde em duas URLs válidas simultâneas, só uma estava na allowlist
  (PR #2).
- **`TABLESAMPLE SYSTEM` não suportado em views**: profiling de view dava
  "Failed to fetch" — query builder passou a omitir `TABLESAMPLE` quando
  `is_view=True` (PR #8).
- **`sm:max-w-sm` do shadcn vencendo `max-w-[...]` customizado**: duas
  rodadas (PR #4, #5) pareceram corrigir a largura do modal de profiling
  sem resolver de fato — causa raiz só foi achada na terceira (PR #6),
  inspecionando o CSS compilado: a ordem das regras no stylesheet gerado
  pelo Tailwind v4, não a ordem no `className`, decide o empate de
  especificidade. Resolvido com `!important` explícito.
- **Dev ficando defasado de `main` silenciosamente**: deploy automático só
  dispara em push que toca os paths do workflow — commits direto em `main`
  (ou merge de branch cortada de um ponto antigo) não disparam redeploy de
  dev. Aconteceu de novo nesta sprint (PR #10/#11), mesma causa já registrada
  no encerramento da sessão anterior. Ainda não virou automação — continua
  sendo descoberto manualmente comparando a tag da imagem rodando contra
  `git log`.
- **Binding de IAM cruzado aplicado sem intenção clara**: nesta sessão, o
  usuário rodou um `add-iam-policy-binding` que dava à SA de prod acesso ao
  BigQuery de dev — comando idêntico ao exemplo estático hardcoded na spec
  `catalog.md` (SA de prod, uma role só), não ao `fix` real que a API
  retornaria (três roles, SA do ambiente que fez a chamada). Esclarecido
  com o usuário, que confirmou a intenção real (Hub observando o outro
  ambiente como projeto-alvo) e pediu pra completar com as roles que
  faltavam nas duas direções.
- **Prod achado com 0 datasets nas sessões anteriores, agora com 3**:
  verificado ao vivo nesta sessão (`GET /projects/observability-hub-prod/
  validate` → `total_datasets: 3`) — a suposição antiga ("0 é esperado, sem
  mock em prod") não é mais verdade. Não investigado a fundo — só uma
  correção de estado registrada aqui pra não repropagar a suposição velha.

---

## Decisões e erros de sessões anteriores (ainda válidos)

1. `INFORMATION_SCHEMA.TABLE_PARTITIONS` não existe em multi-região US/EU e
   não tem o *nome* da coluna de particionamento — usar
   `COLUMNS.is_partitioning_column`.
2. `TABLE_STORAGE.storage_last_modified_time` é o campo correto (não
   `last_modified_time`, `modified_time` nem `last_altered`) — mas ver PR
   #12 acima: catalog/freshness por tabela não usam mais `TABLE_STORAGE`,
   só as visões agregadas por projeto ainda dependem disso.
3. `COLUMN_FIELD_PATHS` é a fonte de `description` de colunas, não `COLUMNS`.
4. `SelectValue` do shadcn/base-ui precisa de render-prop explícito pro
   label — não deriva automaticamente dos `SelectItem` filhos.
5. Antes de qualquer afirmação sobre configuração do BigQuery neste projeto,
   validar ao vivo contra `observability-hub-dev` (ou, quando relevante,
   `observability-hub-prod` — ver erro do "0 datasets" acima).
6. Comandos `gcloud ... add-iam-policy-binding` (e outras mudanças de IAM)
   são bloqueados pelo classificador de auto mode quando o assistant tenta
   rodá-los — sempre passar o comando pronto pro usuário rodar via `!`, um
   comando por vez (colar dois comandos com `!` no mesmo bloco só aplica o
   prefixo no primeiro).
7. Chromium headless não roda neste sandbox (falta `libnspr4.so`, sem
   `sudo` disponível) — recorrente em várias sessões (PR #6, #7, #8, #9,
   #13). Verificação de UI fica limitada a: `tsc`/`vite build`, `biome
   check`, inspeção do CSS/bundle compilado, e teste da API real que o
   componente consome. Sempre declarar explicitamente essa limitação em vez
   de alegar verificação visual que não aconteceu.

---

## Estado da infraestrutura

```
GCP Dev  (observability-hub-dev)
├── Cloud Run: backend — c33f950 pusheado (fix Forbidden/PermissionDenied),
│   deploy automático disparado, ainda não confirmado verde nem revalidado
│   em dev pelo usuário nesta sessão
├── Cloud Run: frontend ✅ tag d9401d2 (branch feat/sprint-3.2, à frente de main)
│   https://frontend-995219021404.us-central1.run.app
├── Artifact Registry: apps ✅ (compartilhado backend+frontend)
├── IAM backend-run@...-dev: metadataViewer + jobUser + dataViewer +
│   logging.viewer no próprio projeto e em observability-hub-prod
│   (cross-project completo — logging.viewer cross adicionado nesta sessão)
├── IAM backend-run@...-prod: as mesmas quatro roles em observability-hub-dev
│   (cross-project completo, idem)
├── Data Access audit logs (DATA_READ, DATA_WRITE, ADMIN_READ) habilitados
│   em dev e prod pra bigquery.googleapis.com — descoberto nesta sessão que
│   já estava assim antes (nunca documentado, ver Backlog itens 8/9/10)
├── Checklist completo de IAM/API/audit config pra onboarding de projeto
│   alvo agora vive em docs/onboarding-cliente.md (criado nesta sessão)
├── Pipeline validado ponta a ponta: 303 testes backend, ruff limpo, biome+
│   tsc+vite build limpos, deploy automático verde a cada push nesta sessão
└── Datasets mock: RAW (3 tabelas), TRUSTED (2 tabelas), REFINED (1 view)

GCP Prod (observability-hub-prod)
├── Cloud Run: backend ✅ tag 44ad7c9 (merge commit do PR #17 — main atual)
├── Cloud Run: frontend ✅ tag 44ad7c9
│   https://frontend-906161007412.us-central1.run.app
├── Artifact Registry: apps ✅ (compartilhado backend+frontend)
├── IAM: ver bloco de dev acima — simétrico nas duas direções, sem lacunas
│   conhecidas no momento
├── total_datasets: 3
└── WIF: attribute_condition restrito a refs/heads/main (só push direto,
    nunca PR) — plan de prod continua revisão manual

GitHub Secrets
├── WIF_PROVIDER_DEV ✅
├── WIF_SA_DEV ✅
├── WIF_PROVIDER_PROD ✅
└── WIF_SA_PROD ✅

Dev está à frente de prod — feat/sprint-3.2 (c33f950) ainda não tem PR
aberto pra main. Prod segue em 44ad7c9 (PR #17, Sprint 3.1).
```

---

## PRs mergeados na Sprint 2

| PR | Branch | Resumo |
|---|---|---|
| #2 | `fix/cors-frontend-alt-url` | CORS pra segunda URL do Cloud Run |
| #3 | `fix/profiling-forbidden-403` | 403 limpo no profiling (Forbidden → ProjectAccessDeniedError) |
| #4 | `fix/profiling-modal-scroll` | Scroll no modal de profiling e na área de SQL |
| #5 | `fix/profiling-modal-layout` | Modal mais largo, SQL colapsável, KPIs com card |
| #6 | `fix/profiling-modal-layout-v2` | Largura real do modal (causa raiz: especificidade do Tailwind v4) |
| #7 | `fix/ux-improvements` | Tabela sem scroll, tipos lógicos, seletor de projeto na topbar, login |
| #8 | `fix/profiling-view-support` | Profiling em views, contagem separada tabelas/views |
| #9 | `feat/profiling-schema-preview` | Schema da tabela no modal antes de estimar/executar |
| #10 | `chore/frontend-dev-redeploy` | Bump de versão pra forçar redeploy em dev |
| #11 | `chore/backend-dev-redeploy` | Bump de versão pra forçar redeploy em dev |
| #12 | `feat/realtime-metadata` | `client.get_table()` pra volumetria/freshness por tabela (esta sessão) |
| #13 | `feature/native-project-badge` | Badge nativo/externo na topbar (esta sessão) |

(PR #1, deploy do frontend no Cloud Run, foi mergeado na sessão anterior e
já estava documentado no encerramento daquela sessão.)

---

## PRs mergeados depois da Sprint 2

| PR | Branch | Resumo |
|---|---|---|
| #16 | `feature/partition-metadata` | Sprint 2.2 + 2.3 completas |
| #17 | `feat/sprint-3.1` | Auth Google OAuth, favoritos, histórico, fixes no modal de profiling |

Sprint 3.2 (esta sessão, branch `feat/sprint-3.2`, commits `5516b36`..
`28f1f7f`) ainda **não tem PR aberto** — aguardando os 7 itens completos e
validados em dev, como pedido explicitamente pelo usuário no início da
sprint.

---

## Backlog / dívida técnica identificada

```
Bloqueantes de nenhuma fase, considerar quando aparecer necessidade:

1. ~~Datasets com apenas views não exibem indicador de freshness na
   sidebar~~ — **obsoleto**: Sprint 2.3 removeu os indicadores de status
   SLA da sidebar por completo (pedido do usuário, não relacionado a este
   item). Não há mais bolinha de nenhum tipo ali.

2. Formalizar IAM (bigquery.metadataViewer/jobUser/dataViewer, incluindo os
   bindings cross-project desta sessão) em Terraform em vez de gcloud
   manual — mais urgente agora que existem 6 bindings manuais por projeto
   (3 roles x 2 SAs) em vez de 2. Fica mais fácil de perder rastro sem IaC.

3. Senha de login hardcoded no frontend (`AuthGate.tsx`, "senha123",
   client-side, sessionStorage) — não é autenticação de verdade, qualquer
   um que leia o bundle JS vê a senha. Aceitável como paywall informal de
   MVP, mas vale substituir antes de expor o Hub além do time interno.

4. Acesso cross-project entre dev e prod (IAM desta sessão): dev faz deploy
   automático em qualquer push sem review, e agora a SA de dev lê dados
   reais de prod. Risco aceito conscientemente pelo usuário nesta sessão —
   revisitar se algum dia incomodar (ex: exigir review antes de deploy em
   dev, ou restringir o binding).

5. Revisitar a restrição de WIF de prod (refs/heads/main) se algum dia for
   necessário automatizar terraform plan de prod em PR.

6. Bundle do frontend passou de 500kB no build (524.80 kB / gzip 166kB) —
   aviso do Vite sobre code-splitting. Não é bloqueante no tamanho atual,
   mas cresce a cada domínio novo (lineage/PII/access vêm na Sprint 3).

7. Actions do CI (`actions/checkout@v4`, `google-github-actions/auth@v2`,
   `google-github-actions/setup-gcloud@v2`) alvo de Node.js 20, GitHub já
   forçando pra Node 24 com aviso de depreciação — sem ação necessária
   agora, mas vale atualizar as actions antes que vire erro.

8. ~~roles/logging.viewer não concedida em dev nem prod~~ — **obsoleto**:
   descoberto nesta sessão (2026-08-14, via `gcloud projects
   get-iam-policy`) que a role já tinha sido concedida self (cada SA no
   próprio projeto) em algum momento entre sessões, sem atualizar este
   arquivo. Cross-project (dev↔prod) foi concedida nesta própria sessão,
   ver "Bug: lineage cross-project" abaixo. Checklist completo (incluindo
   este item) agora vive em `docs/onboarding-cliente.md`.

9. ~~Data Access audit logs desabilitados em dev e prod~~ — **obsoleto**:
   mesma descoberta do item 8, `auditConfigs` já tinha `DATA_READ`,
   `DATA_WRITE` e `ADMIN_READ` habilitados pra `bigquery.googleapis.com`
   nos dois projetos antes desta sessão, também sem registro. Formalizar
   via Terraform (`google_project_iam_audit_config`) continua pendente,
   mas não é mais bloqueante — dado real já flui.

10. ~~Schema dos audit logs nunca validado contra logs reais~~ —
    **obsoleto**: resolvido nos commits `72ed011`/`f18dfab` (depois do
    último `SESSIONLOG` escrito, nunca documentado aqui) — o formato real
    em uso é `AuditData`/`jobCompletedEvent` (legado), não
    `BigQueryAuditMetadata`/`jobChange` como a doc de migração do BQ
    sugeria; parser corrigido, payload real capturado e versionado em
    `tests/unit/lineage/test_repository.py`. Ver docstring de
    `domains/lineage/repository.py`.

11. **Falha de processo recorrente: mudanças de IAM/audit config feitas
    entre sessões sem atualizar o SESSIONLOG** — itens 8/9/10 acima
    ficaram desatualizados por pelo menos uma sessão inteira porque o
    usuário rodou os comandos de IAM/audit config fora do fluxo
    documentado por este arquivo. Mitigação adotada nesta sessão: nova
    seção "Registro de acessos e configurações" no CLAUDE.md + log vivo em
    `docs/onboarding-cliente.md`, para toda concessão de acesso (IAM, API,
    audit config) ser registrada no momento em que acontece, e verificada
    (não assumida) antes de marcar como feita.

11. **Possíveis documentos órfãos na coleção `profiling_results` do
    Firestore de dev** — a feature de score de qualidade escreveu nessa
    coleção enquanto esteve ativa nesta sessão (depois revertida, ver
    Sprint 3.2 acima). Nenhum código lê ou escreve mais nela, mas os
    documentos de teste podem continuar existindo no Firestore até
    alguém limpar manualmente — não afeta nada em runtime, só
    "sujeira" de dado morto.

12. **Bundle do frontend cresceu bastante nesta sessão** — 929.60 kB /
    gzip 281 kB (era 524.80 kB antes da Sprint 3.2), principalmente por
    causa do `recharts` (histórico de qualidade). Item 6 do backlog da
    Sprint 2 (code-splitting) fica mais urgente a cada domínio novo —
    ainda não implementado.
```

---

## Próxima sprint

```
Continuar Sprint 3.2 na branch feat/sprint-3.2 (commits 5516b36..28f1f7f):

1. Usuário valida lineage/órfãs em dev (último item entregue)
2. Fingerprinting de PII — versão resumida da spec antes de implementar
   (preferência já confirmada), depois domains/pii/, endpoint de scan,
   badge na tabela de ativos, botão "Escanear PII" no modal de profiling
3. Mapa de acesso — mesma janela de audit logs de lineage (Cloud Logging,
   Data Access), mesmos pré-requisitos de IAM (item 8/9 do Backlog)
4. Depois dos 7 itens completos e validados: docs/specs/lineage.md,
   pii.md, access.md formais (deferidos pra este momento, por decisão do
   usuário) + CHANGELOG/SESSIONLOG de encerramento + só então pedir
   aprovação pra abrir o PR de feat/sprint-3.2 para main

Fase 4 — FinOps [pendente, depois da Sprint 3.2]
```

---

## Como retomar após reset

1. `cd ~/observability-hub && claude`
2. Claude Code lê CLAUDE.md + SESSIONLOG.md
3. Branch local está em `feat/sprint-3.2`, à frente de `main` em 11
   commits (`5516b36`..`c33f950`) — itens 1, 2 (score, implementado e
   revertido), 3 (histórico), 4 (lineage/órfãs) e o ajuste de UX do
   catálogo (`d9401d2`) completos; fix de bug cross-project em lineage
   (`c33f950`) pusheado, aguardando revalidação do usuário em dev. **Sem PR
   aberto.**
4. Confirmar com o usuário se a revalidação do fix de lineage cross-project
   já aconteceu antes de seguir pro próximo item (PII, item 6 da spec
   original) — apresentar plano resumido antes de escrever qualquer arquivo
   novo, como no restante desta sprint.
5. `docs/onboarding-cliente.md` é o checklist vivo de acesso pra projetos
   alvo (cliente ou dev/prod um observando o outro) — qualquer sessão que
   conceder/alterar IAM, API ou audit config num projeto deve registrar lá
   antes de considerar a tarefa concluída (ver CLAUDE.md, "Registro de
   acessos e configurações").
