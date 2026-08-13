# SESSIONLOG — Observability Hub

Arquivo de continuidade de sessão. Atualizado pelo Claude Code antes de resets.
Lido obrigatoriamente no início de cada nova sessão após um reset.

---

## Status atual

**Última atualização:** 2026-08-13 — Sprint 2.2 e 2.3 concluídas, validadas
em dev, documentação atualizada
**Fase atual:** Sprint 2.2 (metadados de partição + "Ver partições",
refresh, busca reversa) e Sprint 2.3 (sidebar sem bolinhas SLA,
persistência de projeto via localStorage, mode `not_contains` na busca,
resultado da busca em tabela ordenável/filtrável) — **as sete
funcionalidades implementadas, testadas em dev e validadas pelo
usuário**. Tudo na branch `feature/partition-metadata`
(commits `ea64c8d`..`2630fb9`; ver seções "Sprint 2.2" e "Sprint 2.3"
abaixo para o detalhe de cada funcionalidade). Documentação atualizada
nesta sessão (CHANGELOG, PRD, ADR-008, specs de catalog/profiling) — ver
"Sprint 2.2/2.3 — Documentação" abaixo. Um PR (#14) chegou a ser aberto
ainda na primeira versão (incorreta) da Funcionalidade 1 e foi fechado
pelo usuário sem merge — **nenhum PR aberto no momento**, main e prod
inalterados.
**Próximo passo:** Usuário ainda não pediu explicitamente a abertura do
PR de `feature/partition-metadata` para `main` — confirmar antes de abrir
(CLAUDE.md exige aprovação explícita para qualquer `git push`, e abrir PR
é uma ação visível equivalente). Depois do PR (e merge), retomar
**Sprint 3 — Discovery** (Fase 3 do CLAUDE.md): lineage, PII, mapa de
acesso — nenhuma implementação desses domínios foi começada ainda; nenhum
`docs/specs/lineage.md`/`pii.md`/`access.md` existe ainda (checklist do
contexto "Backend" do CLAUDE.md exige spec aprovada antes de implementar).

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
├── Cloud Run: backend ✅ tag 18a9707 (main atual, PR #12+#13 inclusos)
├── Cloud Run: frontend ✅ tag 18a9707 (main atual)
│   https://frontend-995219021404.us-central1.run.app
├── Artifact Registry: apps ✅ (compartilhado backend+frontend)
├── IAM backend-run@...-dev: metadataViewer + jobUser + dataViewer no
│   próprio projeto (PR #3) + as mesmas três em observability-hub-prod
│   (esta sessão, cross-project)
├── IAM backend-run@...-prod: as mesmas três roles em observability-hub-dev
│   (esta sessão, cross-project — ver "IAM cross-project" acima)
├── Pipeline validado ponta a ponta: 190 testes backend, ruff limpo, biome+
│   tsc+vite build limpos, curl direto no Cloud Run confirmando is_native,
│   volumetria em tempo real e classificação de SLA
└── Datasets mock: RAW (3 tabelas), TRUSTED (2 tabelas), REFINED (1 view)

GCP Prod (observability-hub-prod)
├── Cloud Run: backend ✅ tag 5aa7179 (merge commit do PR #13 — main atual)
├── Cloud Run: frontend ✅ tag 5aa7179
│   https://frontend-906161007412.us-central1.run.app
├── Artifact Registry: apps ✅ (compartilhado backend+frontend)
├── IAM: ver bloco de dev acima — simétrico nas duas direções
├── total_datasets: 3 (confirmado ao vivo nesta sessão — ver "Erros
│   encontrados", suposição antiga de "0 datasets" está desatualizada)
└── WIF: attribute_condition restrito a refs/heads/main (só push direto,
    nunca PR) — plan de prod continua revisão manual

GitHub Secrets
├── WIF_PROVIDER_DEV ✅
├── WIF_SA_DEV ✅
├── WIF_PROVIDER_PROD ✅
└── WIF_SA_PROD ✅

Dev e prod estão em sincronia — mesmo código (commit 5aa7179 na linha de
main), ambos os workflows de deploy verdes nos dois ambientes.
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
```

---

## Próxima sprint

```
Antes de tudo: abrir o PR de feature/partition-metadata para main
  (Sprint 2.2 + 2.3 completas, validadas em dev — usuário ainda não pediu
  a abertura, confirmar antes)

Sprint 3 — Discovery (Fase 3 do CLAUDE.md): lineage, PII, mapa de acesso
  [não iniciada — nenhum código, spec ou branch criada ainda]

Fase 4 — FinOps [pendente, depois da Sprint 3]
```

Antes de começar a Sprint 3: seguir o checklist do contexto "Backend" do
CLAUDE.md — ler/criar a spec em `docs/specs/lineage.md` (ou
`pii.md`/`access.md`, conforme o que for priorizado primeiro) antes de
implementar qualquer domínio novo. Nenhuma dessas specs existe ainda em
`docs/specs/`.

---

## Como retomar após reset

1. `cd ~/observability-hub && claude`
2. Claude Code lê CLAUDE.md + SESSIONLOG.md
3. Branch local está em `feature/partition-metadata`, à frente de `main`
   em 9 commits (`ea64c8d`..`2630fb9` + o commit de documentação desta
   seção) — Sprint 2.2 e 2.3 completas e validadas em dev, mas **sem PR
   aberto**. Confirmar com o usuário se já pode abrir o PR para `main`
   antes de qualquer outra ação.
4. Só depois do PR (e merge): confirmar com o usuário qual dos três
   domínios da Sprint 3 (lineage, PII, mapa de acesso) entra primeiro,
   antes de escrever qualquer spec ou código
