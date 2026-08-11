# Spec — Domínio: Catálogo (catalog)

**Versão:** 1.4 (flag is_native em /projects/{project_id}/validate)
**Status:** Aprovada
**Fase:** 2 — MVP v1
**Última atualização:** 2026-08-11 (v1.4)

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
      "location": "US"
    }
  ]
}
```

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

---

## Fora do escopo desta spec

- Busca semântica por nome de tabela
- Lineage (Fase 3)
- Detecção de PII (Fase 3)
- Cache de metadados persistente/compartilhado entre instâncias (o cache
  TTL de 5min de `client.get_table()` é em memória, por processo — ver
  "Fonte de dados")
