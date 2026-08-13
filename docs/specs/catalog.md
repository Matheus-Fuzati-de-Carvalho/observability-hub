# Spec — Domínio: Catálogo (catalog)

**Versão:** 1.5 (metadados de partição, endpoint de partições, busca reversa)
**Status:** Aprovada
**Fase:** 2 — MVP v1 (Sprint 2.2/2.3)
**Última atualização:** 2026-08-13 (v1.5)

---

## Objetivo

Prover um inventário navegável e completo de todos os datasets e tabelas de
qualquer projeto BigQuery acessível pela service account do Hub. A descoberta
de regiões é automática — o backend consulta todas as regiões conhecidas do
BigQuery em paralelo e agrega os resultados. Nenhum parâmetro de região é
necessário nos endpoints.

---

## Fonte de dados

Metadados do INFORMATION_SCHEMA — **custo $0**:

```
<project>.region-<region>.INFORMATION_SCHEMA.SCHEMATA
<project>.region-<region>.INFORMATION_SCHEMA.TABLES
<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE
<project>.region-<region>.INFORMATION_SCHEMA.COLUMNS
```

`GET /catalog/{project_id}/datasets` (resumo por dataset) continua lendo
`num_rows`/`total_size_bytes` de `TABLE_STORAGE` (lag de até 24h, mas uma
única query agregada por região — evita uma chamada de API por tabela do
projeto inteiro).

`GET /catalog/{project_id}/datasets/{dataset_id}/tables` (listagem de
tabelas de um dataset) lê `num_rows`/`size_bytes`/`last_modified_time` via
`client.get_table()` (API REST do BigQuery, tempo real, sem o lag de
`TABLE_STORAGE`) — uma chamada por tabela, em paralelo (`ThreadPoolExecutor`)
e cacheada em memória por 5min (`core/bigquery.py::get_table_cached`/
`get_tables_metadata`) para não bater a API a cada refresh de tela.
`TABLE_PARTITIONS` não é mais usada (ver Query 3).

`GET /catalog/{project_id}/datasets/{dataset_id}/tables` também busca
min/max/contagem de partição (`partition_type`, `min_partition`,
`max_partition`, `partition_count`) para as tabelas com
`is_partitioned=true`, uma tabela por vez em paralelo
(`ThreadPoolExecutor`). Diferente do resto desta spec, **essa não é uma
query de metadado gratuita** — é `MIN`/`MAX`/`COUNT(DISTINCT)` direto na
coluna de partição (`SELECT ... FROM {project}.{dataset}.{tabela}`), com
custo real de bytes escaneados (mitigado por ler só uma coluna, sem
filtro). `INFORMATION_SCHEMA.PARTITIONS` foi avaliada e descartada como
fonte: não existe para datasets multi-região (US/EU), que é onde estão
todos os datasets de dev e prod hoje — teria retornado N/D sempre, sem
valor prático (ver CHANGELOG, Sprint 2.2). Por ter custo real, o
resultado é cacheado em memória por 5min por tabela
(`domains/catalog/repository.py::_partition_stats_cache`, TTL local ao
domínio catalog, mesmo padrão do `get_table_cached` de `core/bigquery.py`
mas não compartilhado com ele).

`GET /catalog/{project_id}/search` (busca reversa) consulta
`INFORMATION_SCHEMA.TABLES` de todas as regiões descobertas via
`discover_regions()`, em paralelo — uma query por região, metadado
gratuito, mesma técnica de `discover_regions`.

Lista de regiões mantida em `core/config.py`:
```python
BQ_REGIONS = [
    "US", "EU",
    "us-central1", "us-east1", "us-east4", "us-west1", "us-west2",
    "us-west3", "us-west4", "northamerica-northeast1",
    "southamerica-east1", "europe-west1", "europe-west2",
    "europe-west3", "europe-west4", "europe-west6",
    "europe-north1", "asia-east1", "asia-east2",
    "asia-northeast1", "asia-northeast2", "asia-northeast3",
    "asia-south1", "asia-southeast1", "asia-southeast2",
    "australia-southeast1",
]
```

---

## Endpoints da API

### GET /api/v1/projects/{project_id}/validate
Valida acesso e descobre automaticamente as regiões com datasets.

`is_native` indica se `project_id` é o projeto GCP onde esta instância do
Hub está rodando (`client.project`, resolvido via `GOOGLE_CLOUD_PROJECT` ou
`google.auth.default()` — mesma fonte usada no `fix` da Response 403
abaixo). Usado pelo frontend para diferenciar "Hub observando a si mesmo"
(dev observando `observability-hub-dev`, prod observando
`observability-hub-prod`) de "Hub observando um projeto externo" (ex: prod
observando `observability-hub-dev` como projeto-alvo, ou vice-versa).

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "accessible": true,
  "available_regions": ["US"],
  "total_datasets": 3,
  "is_native": true
}
```

**Response 403:**
```json
{
  "error": "access_denied",
  "message": "A service account do Hub não tem acesso a este projeto.",
  "fix": "gcloud projects add-iam-policy-binding {project_id} --member='serviceAccount:backend-run@observability-hub-prod.iam.gserviceaccount.com' --role='roles/bigquery.metadataViewer'"
}
```

**Response 404:**
```json
{
  "error": "project_not_found",
  "message": "Projeto não encontrado ou não existe."
}
```

---

### GET /api/v1/catalog/{project_id}/datasets
Lista todos os datasets agregando todas as regiões automaticamente.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "evaluated_at": "2026-08-05T10:00:00Z",
  "total_datasets": 3,
  "regions_found": ["US"],
  "datasets": [
    {
      "dataset_id": "RAW",
      "location": "US",
      "creation_time": "2026-06-03T19:40:00Z",
      "last_modified_time": "2026-06-08T18:38:00Z",
      "total_tables": 3,
      "total_views": 0,
      "total_size_bytes": 2075443,
      "total_size_gb": 0.002,
      "total_rows": 30000
    }
  ]
}
```

---

### GET /api/v1/catalog/{project_id}/datasets/{dataset_id}/tables
Lista tabelas do dataset. Região descoberta automaticamente via metadados.

**Parâmetros opcionais:**
- `table_type` (query) — `TABLE`, `VIEW`, `EXTERNAL`, `MATERIALIZED_VIEW`

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "dataset_id": "RAW",
  "location": "US",
  "total_tables": 3,
  "tables": [
    {
      "table_id": "ga4_events",
      "table_type": "TABLE",
      "creation_time": "2026-06-08T18:38:40Z",
      "last_modified_time": "2026-06-08T18:38:40Z",
      "size_bytes": 576920,
      "size_gb": 0.0005,
      "row_count": 10000,
      "column_count": 8,
      "is_partitioned": false,
      "partition_column": null,
      "is_clustered": false,
      "clustering_columns": [],
      "location": "US",
      "partition_type": null,
      "min_partition": null,
      "max_partition": null,
      "partition_count": null
    }
  ]
}
```

`partition_type`/`min_partition`/`max_partition`/`partition_count` só são
preenchidos quando `is_partitioned=true` (`null` caso contrário).
`partition_type` vem de `client.get_table().time_partitioning`/
`range_partitioning`, ex: `"event_date (DAY)"` — sem custo extra, já
reaproveita o `client.get_table()` cacheado que a listagem já faz para
`row_count`/`size_bytes`/`last_modified_time`.

---

### GET /api/v1/catalog/{project_id}/datasets/{dataset_id}/tables/{table_id}/partitions
Lista as partições distintas de uma tabela particionada com a contagem de
linhas de cada uma — query real (`GROUP BY` na coluna de partição),
ordenada da mais recente para a mais antiga.

**Response 200:**
```json
{
  "table_id": "events",
  "partition_column": "event_date",
  "partition_type": "event_date (DAY)",
  "total_partitions": 3,
  "partitions": [
    { "value": "2021-01-30", "row_count": 3161 },
    { "value": "2021-01-03", "row_count": 24743 },
    { "value": "2021-01-01", "row_count": 22096 }
  ]
}
```

**Response 400** (tabela não particionada):
```json
{
  "error": "table_not_partitioned",
  "message": "Tabela 'crm_leads' em 'observability-hub-dev.RAW' não é particionada."
}
```

---

### GET /api/v1/catalog/{project_id}/search
Busca reversa: em quais datasets do projeto existe (ou não) uma tabela com
um determinado nome. Caso de uso principal: projetos GA4 com múltiplos
datasets (`analytics_<id>`) recebendo tabelas `events_YYYYMMDD` diariamente
— descobrir em quais datasets a partição do dia já chegou.

**Parâmetros:**
- `q` (query, obrigatório) — termo de busca, mínimo 1 caractere
- `mode` (query, default `exact`) — `exact`, `contains` ou `not_contains`

| Mode | Lógica |
|---|---|
| `exact` | `table_name = q`, em todas as regiões do projeto |
| `contains` | `table_name LIKE '%q%'` |
| `not_contains` | Inverte a pergunta: retorna os datasets onde **nenhuma** tabela contém `q` (não lista tabelas individuais) |

**Response 200** (`mode=exact`, tabela existe em alguns datasets, ausente
em outros da mesma série):
```json
{
  "query": "events_20260813",
  "mode": "exact",
  "project_id": "observability-hub-dev",
  "datasets_with_match": [],
  "datasets_without_match": [
    {
      "dataset_id": "analytics_100001",
      "reason": "prefix_exists",
      "latest_partition": "events_20260812"
    }
  ]
}
```

`datasets_with_match` traz `last_modified_time` e `row_count` reais via
`client.get_table()` (mesma técnica de cache/paralelismo de
`get_tables_metadata`, ver "Fonte de dados"). `datasets_without_match`
**não** lista todo dataset do projeto que não bateu — só os que têm outra
tabela da mesma série: o prefixo é derivado removendo o sufixo numérico
final de `q` (`"events_20260812"` → `"events_"`,
`domains/catalog/repository.py::derive_search_prefix`), buscado via
`GROUP BY` + `MAX(table_name)` por dataset. Sem sufixo numérico em `q`
(ex: `"ga4_events"`), não há "série" pra comparar e o campo fica vazio.

Para `mode=not_contains`, `datasets_with_match` fica sempre vazio (não há
uma tabela específica pra apontar como "match" nesse mode) e
`datasets_without_match` lista **todos** os datasets do projeto sem
nenhuma tabela contendo `q`, com `reason="no_match"` e
`latest_partition=null` — a lógica de prefixo/série não se aplica aqui.

---

### GET /api/v1/catalog/{project_id}/datasets/{dataset_id}/tables/{table_id}
Detalhe completo com schema de colunas.

**Response 200** (campos adicionais):
```json
{
  "columns": [
    {
      "column_name": "event_date",
      "data_type": "STRING",
      "is_nullable": true,
      "description": null
    }
  ],
  "labels": {},
  "description": null
}
```

---

## Lógica de descoberta de regiões

```python
# core/bigquery.py
async def discover_regions(project_id: str) -> list[str]:
    """
    Tenta INFORMATION_SCHEMA.SCHEMATA em cada região conhecida em paralelo.
    Retorna apenas as regiões onde o projeto tem datasets.
    Ignora erros de 'não encontrado' (sem datasets naquela região).
    Lança PermissionError se nenhuma região retornar dados por falta de acesso.
    """
```

---

## Queries BigQuery

### Query 1 — Descoberta de regiões (executada por região em paralelo)
```sql
SELECT schema_name, location
FROM `<project>.region-<region>.INFORMATION_SCHEMA.SCHEMATA`
LIMIT 1
```

### Query 2 — Resumo de datasets
```sql
SELECT
  s.schema_name                                          AS dataset_id,
  s.location,
  s.creation_time,
  s.last_modified_time,
  COUNTIF(t.table_type = 'BASE TABLE')                   AS total_tables,
  COUNTIF(t.table_type IN ('VIEW','MATERIALIZED VIEW'))  AS total_views,
  COALESCE(SUM(ts.total_logical_bytes), 0)               AS total_size_bytes,
  COALESCE(SUM(ts.total_rows), 0)                        AS total_rows
FROM `<project>.region-<region>.INFORMATION_SCHEMA.SCHEMATA` s
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLES` t
  ON t.table_schema = s.schema_name
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE` ts
  ON ts.table_schema = t.table_schema
 AND ts.table_name   = t.table_name
GROUP BY 1, 2, 3, 4
ORDER BY total_size_bytes DESC
```

### Query 3 — Tabelas de um dataset

Metadados estruturais (via SQL, `INFORMATION_SCHEMA.TABLES` + `COLUMNS` —
`TABLE_PARTITIONS` não é usada: não tem o nome da coluna de particionamento e
não existe em US/EU; `column_count`/`partition_column`/`clustering_columns`
vêm de `COLUMNS.is_partitioning_column`/`clustering_ordinal_position`):

```sql
SELECT
  t.table_name,
  t.table_type,
  t.creation_time,
  COUNT(c.column_name)                                        AS column_count,
  MAX(CASE WHEN c.is_partitioning_column = 'YES'
        THEN c.column_name END)                                AS partition_column
FROM `<project>.region-<region>.INFORMATION_SCHEMA.TABLES` t
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.COLUMNS` c
  ON c.table_name = t.table_name AND c.table_schema = t.table_schema
WHERE t.table_schema = @dataset_id
GROUP BY 1, 2, 3
```

`num_rows`/`size_bytes`/`last_modified_time` vêm de `client.get_table()`
(uma chamada por `table_name` retornado acima, em paralelo, cacheada 5min —
ver "Fonte de dados"), não de SQL. O `ORDER BY size_bytes DESC NULLS LAST` é
aplicado em Python depois do merge, já que `size_bytes` não vem mais da
query.

### Query 4 — Min/max/contagem de partição (só tabelas com is_partitioned=true)
```sql
SELECT
  MIN(`{campo}`)            AS min_partition,
  MAX(`{campo}`)            AS max_partition,
  COUNT(DISTINCT `{campo}`) AS partition_count
FROM `{project}.{dataset}.{tabela}`
```
`{campo}` é o `partition_column` já resolvido na Query 3. Diferente das
demais queries desta spec, **não** é `region-qualified` nem gratuita (ver
"Fonte de dados").

### Query 5 — Listagem de partições distintas (endpoint /partitions)
```sql
SELECT `{campo}` AS partition_value, COUNT(*) AS row_count
FROM `{project}.{dataset}.{tabela}`
GROUP BY 1
ORDER BY 1 DESC
```

### Query 6 — Busca reversa (endpoint /search)
```sql
-- mode=exact
SELECT table_schema AS dataset_id, table_name AS table_id, table_type
FROM `{project}.region-{region}.INFORMATION_SCHEMA.TABLES`
WHERE table_name = @q

-- mode=contains
... WHERE table_name LIKE @q  -- @q = '%{q}%'
```
Uma query por região, em paralelo. `mode=not_contains` não usa essa forma
— compara o conjunto de datasets do projeto inteiro (Query 2, sem o
`JOIN`/agregação) contra o resultado de `mode=contains`.

```sql
-- prefixo (datasets_without_match de exact/contains)
SELECT table_schema AS dataset_id, MAX(table_name) AS latest_table
FROM `{project}.region-{region}.INFORMATION_SCHEMA.TABLES`
WHERE table_name LIKE @prefix  -- @prefix = '{prefixo}%'
GROUP BY 1
```

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   ├── projects.py       # GET /projects/{project_id}/validate
│   └── catalog.py
├── core/
│   ├── config.py         # BQ_REGIONS e demais configs
│   └── bigquery.py       # discover_regions(), get_client()
├── domains/catalog/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py
│   └── schemas.py
└── tests/unit/catalog/
    ├── test_service.py
    └── test_schemas.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Projeto sem permissão | HTTP 403 com comando de correção |
| Projeto inexistente | HTTP 404 |
| Projeto com datasets em múltiplas regiões | Todos retornados, cada um com seu `location` |
| Dataset sem tabelas | `total_tables: 0`, lista vazia |
| Tabela externa | Incluída, `size_bytes` pode ser null |
| View | Incluída, `row_count` e `size_bytes` null |
| `/partitions` numa tabela não particionada | HTTP 400 `table_not_partitioned` |
| `/search` sem sufixo numérico em `q` | `datasets_without_match` vazio (exact/contains) — não há série pra comparar |
| `/search?mode=not_contains` | `datasets_with_match` sempre vazio; `datasets_without_match` lista todo dataset sem tabela contendo `q` |

---

## Fora do escopo desta spec

- Busca semântica/fuzzy por nome de tabela (`/search` é exata ou substring
  literal — `exact`/`contains`/`not_contains`, sem fuzzy matching nem
  regex)
- Lineage (Fase 3)
- Detecção de PII (Fase 3)
- Cache de metadados persistente/compartilhado entre instâncias (os caches
  TTL de `client.get_table()` e de `get_partition_stats` são em memória,
  por processo — ver "Fonte de dados")
