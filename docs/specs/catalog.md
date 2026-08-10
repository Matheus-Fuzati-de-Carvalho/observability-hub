# Spec — Domínio: Catálogo (catalog)

**Status:** Draft para revisão
**Fase:** 2 — MVP
**Última atualização:** 2026-08-05

---

## Objetivo

Prover um inventário navegável e completo de todos os datasets e tabelas de um
projeto BigQuery, exibindo volumetria, tipo, região e metadados de tempo —
sem executar queries em dados reais, apenas em metadados do INFORMATION_SCHEMA.

---

## Fonte de dados

Todas as informações vêm exclusivamente de:

```sql
-- Datasets
`<project>.region-<region>.INFORMATION_SCHEMA.SCHEMATA`

-- Tabelas e views
`<project>.region-<region>.INFORMATION_SCHEMA.TABLES`
`<project>.region-<region>.INFORMATION_SCHEMA.TABLE_OPTIONS`

-- Tamanho e contagem de linhas (metadados, sem scan de dados)
`<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE`
```

Custo: metadados do INFORMATION_SCHEMA são **gratuitos** no BigQuery.

---

## Endpoints da API

### GET /api/v1/catalog/projects
Lista os projetos GCP disponíveis para o usuário autenticado.

**Response:**
```json
{
  "projects": [
    { "project_id": "observability-hub-dev", "display_name": "Observability Hub Dev" }
  ]
}
```

---

### GET /api/v1/catalog/{project_id}/datasets
Lista todos os datasets de um projeto com resumo de volumetria.

**Parâmetros:**
- `project_id` (path) — ID do projeto GCP
- `region` (query, default: `us-central1`) — região do dataset

**Response:**
```json
{
  "project_id": "observability-hub-dev",
  "region": "us-central1",
  "total_datasets": 3,
  "datasets": [
    {
      "dataset_id": "analytics",
      "location": "US",
      "creation_time": "2024-01-15T10:00:00Z",
      "last_modified_time": "2024-06-01T08:30:00Z",
      "total_tables": 12,
      "total_views": 3,
      "total_size_bytes": 1073741824,
      "total_size_gb": 1.07,
      "total_rows": 5000000
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
- `table_type` (query, opcional) — filtro: `TABLE`, `VIEW`, `EXTERNAL`, `MATERIALIZED_VIEW`

**Response:**
```json
{
  "project_id": "observability-hub-dev",
  "dataset_id": "analytics",
  "total_tables": 12,
  "tables": [
    {
      "table_id": "events",
      "table_type": "TABLE",
      "creation_time": "2024-01-15T10:00:00Z",
      "last_modified_time": "2024-06-01T08:00:00Z",
      "size_bytes": 536870912,
      "size_gb": 0.54,
      "row_count": 2500000,
      "is_partitioned": true,
      "partition_column": "_PARTITIONTIME",
      "partition_type": "DAY",
      "is_clustered": true,
      "clustering_columns": ["event_name", "user_pseudo_id"]
    }
  ]
}
```

---

### GET /api/v1/catalog/{project_id}/datasets/{dataset_id}/tables/{table_id}
Detalhe completo de uma tabela específica.

**Response adicional ao item acima:**
```json
{
  "columns": [
    {
      "column_name": "event_name",
      "data_type": "STRING",
      "is_nullable": true,
      "description": "Nome do evento GA4"
    }
  ],
  "labels": {
    "env": "prod",
    "team": "analytics"
  },
  "description": "Eventos brutos do GA4"
}
```

---

## Queries BigQuery planejadas

### Query 1 — Resumo de datasets
```sql
SELECT
  s.schema_name                          AS dataset_id,
  s.location,
  s.creation_time,
  s.last_modified_time,
  COUNT(DISTINCT t.table_name)           AS total_tables,
  COALESCE(SUM(ts.total_rows), 0)        AS total_rows,
  COALESCE(SUM(ts.total_logical_bytes), 0) AS total_size_bytes
FROM `<project>.region-<region>.INFORMATION_SCHEMA.SCHEMATA` s
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLES` t
  ON t.table_schema = s.schema_name
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE` ts
  ON ts.table_schema = t.table_schema
 AND ts.table_name  = t.table_name
GROUP BY 1, 2, 3, 4
ORDER BY total_size_bytes DESC
```
**Custo estimado:** $0 (metadados)

### Query 2 — Tabelas de um dataset
```sql
SELECT
  t.table_name,
  t.table_type,
  t.creation_time,
  t.last_modified_time,
  ts.total_rows,
  ts.total_logical_bytes,
  tp.partition_expiration_days,
  tp.partition_column,
FROM `<project>.region-<region>.INFORMATION_SCHEMA.TABLES` t
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE` ts
  ON ts.table_name = t.table_name AND ts.table_schema = t.table_schema
LEFT JOIN `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_PARTITIONS` tp
  ON tp.table_name = t.table_name AND tp.table_schema = t.table_schema
WHERE t.table_schema = @dataset_id
GROUP BY 1,2,3,4,5,6,7,8
ORDER BY ts.total_logical_bytes DESC
```
**Custo estimado:** $0 (metadados)

---

## Estrutura de arquivos a criar

```
apps/backend/src/observability_hub/
├── api/
│   └── v1/
│       └── catalog.py          # Router FastAPI — só HTTP, sem lógica
├── domains/
│   └── catalog/
│       ├── __init__.py
│       ├── service.py          # Lógica principal, chama o repository
│       ├── repository.py       # Queries BQ — única camada que toca GCP
│       └── schemas.py          # Pydantic models de request/response
└── tests/
    └── unit/
        └── catalog/
            ├── test_service.py     # Testa lógica com mocks do repository
            └── test_schemas.py     # Testa validação dos Pydantic models
```

---

## Casos de borda

| Cenário | Comportamento esperado |
|---|---|
| Projeto sem datasets | Retorna `total_datasets: 0`, lista vazia |
| Dataset sem tabelas | Retorna `total_tables: 0`, lista vazia |
| Tabela externa (EXTERNAL) | Inclui na listagem, `size_bytes` pode ser null |
| View | Inclui na listagem, `row_count` e `size_bytes` são null |
| Sem permissão no projeto | HTTP 403 com mensagem clara |
| Projeto inexistente | HTTP 404 |
| Região incorreta | HTTP 400 com sugestão de regiões válidas |

---

## Fora do escopo desta spec

- Busca semântica por nome de tabela (Fase futura)
- Lineage de tabelas (Fase 3)
- Detecção de PII nas colunas (Fase 3)
- Cache de metadados (avaliar na Fase 2 conforme performance)
- Suporte a múltiplas regiões em uma única chamada
