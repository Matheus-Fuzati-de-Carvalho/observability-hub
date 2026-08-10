# Spec — Domínio: Catálogo (catalog)

**Versão:** 1.1 (atualizada com cross-project e validate endpoint)
**Status:** Aprovada
**Fase:** 2 — MVP v1
**Última atualização:** 2026-08-05

---

## Objetivo

Prover um inventário navegável e completo de todos os datasets e tabelas de
qualquer projeto BigQuery acessível pela service account do Hub, exibindo
volumetria, tipo, região e metadados de tempo — sem queries em dados reais,
apenas em metadados do INFORMATION_SCHEMA.

O projeto alvo é informado pelo usuário via campo no frontend (cross-project,
conforme ADR-006) e validado antes de carregar o catálogo.

---

## Fonte de dados

Todas as informações vêm exclusivamente de metadados — **custo $0**:

```sql
`<project>.region-<region>.INFORMATION_SCHEMA.SCHEMATA`
`<project>.region-<region>.INFORMATION_SCHEMA.TABLES`
`<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE`
`<project>.region-<region>.INFORMATION_SCHEMA.TABLE_PARTITIONS`
`<project>.region-<region>.INFORMATION_SCHEMA.COLUMNS`
```

---

## Endpoints da API

### GET /api/v1/projects/{project_id}/validate
Valida se o projeto existe e se a SA tem acesso antes de carregar o catálogo.
Chamado pelo frontend ao submeter o seletor de projeto.

**Parâmetros:**
- `project_id` (path) — ID do projeto GCP alvo

**Response 200:**
```json
{
  "project_id": "cliente-x-prod",
  "accessible": true,
  "default_region": "us-central1",
  "available_regions": ["us-central1", "us-east1"]
}
```

**Response 403:**
```json
{
  "error": "access_denied",
  "message": "A service account do Hub não tem acesso a este projeto.",
  "fix": "gcloud projects add-iam-policy-binding cliente-x-prod --member='serviceAccount:backend-run@observability-hub-prod.iam.gserviceaccount.com' --role='roles/bigquery.metadataViewer'"
}
```

**Response 404:**
```json
{
  "error": "project_not_found",
  "message": "Projeto 'cliente-x-prod' não encontrado ou não existe."
}
```

---

### GET /api/v1/catalog/{project_id}/datasets
Lista todos os datasets de um projeto com resumo de volumetria.

**Parâmetros:**
- `project_id` (path)
- `region` (query, default: `us-central1`)

**Response 200:**
```json
{
  "project_id": "cliente-x-prod",
  "region": "us-central1",
  "total_datasets": 3,
  "datasets": [
    {
      "dataset_id": "RAW",
      "location": "US",
      "creation_time": "2024-01-15T10:00:00Z",
      "last_modified_time": "2024-06-01T08:30:00Z",
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
Lista todas as tabelas de um dataset com metadados detalhados.

**Parâmetros:**
- `project_id` (path)
- `dataset_id` (path)
- `region` (query, default: `us-central1`)
- `table_type` (query, opcional) — `TABLE`, `VIEW`, `EXTERNAL`, `MATERIALIZED_VIEW`

**Response 200:**
```json
{
  "project_id": "cliente-x-prod",
  "dataset_id": "RAW",
  "total_tables": 3,
  "tables": [
    {
      "table_id": "crm_leads_mock",
      "table_type": "TABLE",
      "creation_time": "2026-06-08T18:27:49Z",
      "last_modified_time": "2026-06-08T18:27:49Z",
      "size_bytes": 849813,
      "size_gb": 0.0008,
      "row_count": 10000,
      "column_count": 6,
      "is_partitioned": false,
      "partition_column": null,
      "partition_type": null,
      "is_clustered": false,
      "clustering_columns": [],
      "region": "US"
    }
  ]
}
```

---

### GET /api/v1/catalog/{project_id}/datasets/{dataset_id}/tables/{table_id}
Detalhe completo de uma tabela incluindo schema de colunas.

**Response 200** (campos adicionais ao item acima):
```json
{
  "columns": [
    {
      "column_name": "lead_id",
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

## Queries BigQuery planejadas

### Query 1 — Validação de acesso ao projeto
```sql
SELECT schema_name
FROM `<project>.region-<region>.INFORMATION_SCHEMA.SCHEMATA`
LIMIT 1
```
Custo: $0. Se lançar exceção de permissão → 403. Se projeto não existir → 404.

### Query 2 — Resumo de datasets
```sql
SELECT
  s.schema_name                              AS dataset_id,
  s.location,
  s.creation_time,
  s.last_modified_time,
  COUNTIF(t.table_type = 'BASE TABLE')       AS total_tables,
  COUNTIF(t.table_type IN ('VIEW','MATERIALIZED VIEW')) AS total_views,
  COALESCE(SUM(ts.total_logical_bytes), 0)   AS total_size_bytes,
  COALESCE(SUM(ts.total_rows), 0)            AS total_rows
FROM `<project>.region-<region>.INFORMATION_SCHEMA.SCHEMATA` s
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLES` t
  ON t.table_schema = s.schema_name
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE` ts
  ON ts.table_schema = t.table_schema
 AND ts.table_name   = t.table_name
GROUP BY 1, 2, 3, 4
ORDER BY total_size_bytes DESC
```
Custo: $0

### Query 3 — Tabelas de um dataset
```sql
SELECT
  t.table_name,
  t.table_type,
  t.creation_time,
  t.last_modified_time,
  ts.total_rows        AS row_count,
  ts.total_logical_bytes AS size_bytes,
  COUNT(c.column_name) AS column_count,
  MAX(CASE WHEN tp.partition_column IS NOT NULL
      THEN tp.partition_column END) AS partition_column,
  MAX(tp.partition_expiration_days)  AS partition_expiration_days
FROM `<project>.region-<region>.INFORMATION_SCHEMA.TABLES` t
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE` ts
  ON ts.table_name   = t.table_name
 AND ts.table_schema = t.table_schema
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.COLUMNS` c
  ON c.table_name   = t.table_name
 AND c.table_schema = t.table_schema
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_PARTITIONS` tp
  ON tp.table_name   = t.table_name
 AND tp.table_schema = t.table_schema
WHERE t.table_schema = @dataset_id
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY size_bytes DESC NULLS LAST
```
Custo: $0

---

## Estrutura de arquivos a criar

```
apps/backend/src/observability_hub/
├── api/v1/
│   ├── projects.py       # GET /projects/{project_id}/validate
│   └── catalog.py        # GET /catalog/...
├── domains/catalog/
│   ├── __init__.py
│   ├── service.py        # Lógica principal
│   ├── repository.py     # Queries BQ
│   └── schemas.py        # Pydantic models
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
| Região incorreta | HTTP 400 com regiões válidas sugeridas |
| Dataset sem tabelas | `total_tables: 0`, lista vazia |
| Tabela externa (EXTERNAL) | Incluída, `size_bytes` pode ser null |
| View | Incluída, `row_count` e `size_bytes` null |

---

## Fora do escopo desta spec

- Busca semântica por nome de tabela
- Lineage (Fase 3)
- Detecção de PII (Fase 3)
- Cache de metadados
- Suporte a múltiplas regiões em uma única chamada
