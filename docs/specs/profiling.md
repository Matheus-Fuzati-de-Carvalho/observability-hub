# Spec — Domínio: Profiling (quality)

**Versão:** 1.2 (suporte a views, tipo lógico por tipo físico, schema preview)
**Status:** Aprovada
**Fase:** 2 — MVP v1
**Última atualização:** 2026-08-13

---

## Objetivo

Análise estatística configurável de qualquer tabela BigQuery, coluna a coluna,
com controles de amostragem, filtro temporal e estimativa de custo antes da
execução. A região é resolvida automaticamente via metadados do dataset.

---

## Fluxo de uso

```
1. Usuário clica em "Analisar" em uma tabela do catálogo
2. Modal abre com o schema da tabela já carregado (GET .../tables/{table_id}
   do domínio catalog, reaproveitado — ver "Schema preview" abaixo),
   destacando coluna de partição e badges "Particionada por"/"Clusterizada por"
3. Configura: amostragem %, método unicidade, coluna de data, janela
   (amostragem desabilitada se a tabela for VIEW/MATERIALIZED VIEW — ver
   "Suporte a views")
4. "Estimar Custo" → dry run retorna volume e custo USD + SQL gerado
5. "Executar Profile" → métricas por coluna e resumo da tabela
6. Opcional: drill down "Distribuição de nulos ao longo do tempo"
```

### Schema preview (frontend, antes de estimar/executar)

O modal carrega o schema completo da tabela (`GET /api/v1/catalog/
{project_id}/datasets/{dataset_id}/tables/{table_id}`, endpoint do domínio
catalog — não é um endpoint novo de profiling) antes de qualquer
estimativa ou execução, numa tabela Nome/Tipo/Nullable
(`SchemaTable.tsx`). Colunas `STRUCT`/`ARRAY` aparecem com badge
"Complexo" (mesmo critério de exclusão do profiling, `sql_builder.
is_excluded_type` — prefixo `STRUCT<`/`ARRAY<` no `data_type`), mas
**mostradas no schema mesmo assim**, sem métricas — só o profiling em si
as exclui e reporta em `excluded_columns` (ver "Casos de borda"). Colunas
de data ganham destaque visual. Header do modal mostra badges "Particionada
por {coluna}"/"Clusterizada por {colunas}" quando aplicável.

### Suporte a views

`TABLESAMPLE SYSTEM` não é suportado pelo BigQuery em `VIEW`/
`MATERIALIZED VIEW` — `is_view` (resolvido via `INFORMATION_SCHEMA.TABLES.
table_type`, `domains/quality/repository.py::is_view`) é passado para
`sql_builder.build_main_query`/`build_top_n_query`, que omitem a cláusula
`TABLESAMPLE` (e ignoram `sample_percent`) quando `is_view=true`. O
frontend desabilita o campo de amostragem com um aviso quando a tabela é
view.

---

## Parâmetros de configuração

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `sample_percent` | float | 100 | % TABLESAMPLE SYSTEM (mín: 1) |
| `uniqueness_method` | enum | `approx` | `approx` (HLL) ou `exact` (DISTINCT) |
| `date_column` | string | null | Coluna de data para filtro temporal |
| `date_window_days` | int | null | Janela em dias (D-X dias até hoje) |

---

## Endpoints da API

### POST /api/v1/profiling/{project_id}/{dataset_id}/{table_id}/estimate
Dry run — bytes e custo estimados sem executar query real.

**Body:**
```json
{
  "sample_percent": 10,
  "uniqueness_method": "approx",
  "date_column": "date",
  "date_window_days": 365
}
```

**Response 200:**
```json
{
  "estimated_bytes": 849813,
  "estimated_bytes_human": "830.13 KB",
  "estimated_cost_usd": 0.000005,
  "sql": "SELECT COUNT(*) AS _total_sampled_rows, ..."
}
```

---

### POST /api/v1/profiling/{project_id}/{dataset_id}/{table_id}/run
Executa profiling e retorna métricas completas.

**Body:** mesmo schema do `/estimate`

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "dataset_id": "RAW",
  "table_id": "crm_leads",
  "executed_at": "2026-08-05T10:00:00Z",
  "parameters": {
    "sample_percent": 10,
    "uniqueness_method": "approx",
    "date_column": "date",
    "date_window_days": 365
  },
  "sql": "...",
  "table_summary": {
    "total_sampled_rows": 10000,
    "total_table_rows": 10000,
    "estimated_duplicate_rows": 474,
    "estimated_duplicate_pct": 4.74,
    "overall_density": 100.0
  },
  "columns": [
    {
      "column_name": "lead_status",
      "data_type": "STRING",
      "is_nullable": true,
      "completeness_pct": 100.0,
      "null_count": 0,
      "distinct_count": 4,
      "distinct_pct": 0.04,
      "min_value": "lead",
      "max_value": "venda_concluida",
      "top_values": [
        { "value": "lead", "count": 4200, "pct": 42.0 },
        { "value": "qualificado", "count": 3100, "pct": 31.0 },
        { "value": "proposta", "count": 1800, "pct": 18.0 },
        { "value": "venda_concluida", "count": 900, "pct": 9.0 }
      ],
      "inferred_logical_type": "categorical",
      "coefficient_of_variation": null,
      "quality_flag": "ok"
    }
  ]
}
```

---

### GET /api/v1/profiling/{project_id}/{dataset_id}/{table_id}/null-distribution
Drill down: distribuição de nulos ao longo do tempo por coluna.

**Parâmetros:**
- `column_name` (query, obrigatório)
- `date_column` (query, obrigatório)
- `date_window_days` (query, default: 30)
- `granularity` (query, default: `day`) — `day`, `week`, `month`

**Response 200:**
```json
{
  "column_name": "email",
  "date_column": "date",
  "granularity": "day",
  "series": [
    { "period": "2026-07-01", "null_count": 0, "null_pct": 0.0, "total_rows": 450 },
    { "period": "2026-07-02", "null_count": 12, "null_pct": 2.8, "total_rows": 430 }
  ]
}
```

---

## Lógica de geração de SQL

### Query principal (gerada dinamicamente)
```sql
SELECT
  COUNT(*) AS _total_sampled_rows,

  -- Por coluna:
  COUNT(`{col}`)                      AS {col}__count_filled,
  APPROX_COUNT_DISTINCT(`{col}`)      AS {col}__approx_distinct,  -- se approx
  COUNT(DISTINCT `{col}`)             AS {col}__exact_distinct,   -- se exact
  MIN(`{col}`)                        AS {col}__min,
  MAX(`{col}`)                        AS {col}__max,
  -- Apenas para numéricos:
  AVG(CAST(`{col}` AS FLOAT64))       AS {col}__avg,
  STDDEV(CAST(`{col}` AS FLOAT64))    AS {col}__stddev

FROM `{project}.{dataset}.{table}`
  TABLESAMPLE SYSTEM ({sample_percent} PERCENT)
WHERE `{date_column}` >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
```

### Top N valores (só para colunas com distinct_count < 50)
```sql
SELECT `{col}` AS value, COUNT(*) AS count
FROM `{project}.{dataset}.{table}`
  TABLESAMPLE SYSTEM ({sample_percent} PERCENT)
WHERE `{date_column}` >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
GROUP BY 1
ORDER BY count DESC
LIMIT 10
```

Ambas as queries acima omitem `TABLESAMPLE SYSTEM (...)` (e ignoram
`sample_percent`) quando a tabela é `VIEW`/`MATERIALIZED VIEW` — ver
"Suporte a views".

---

## Regras das métricas

### Tipo lógico inferido (sem custo extra — usa min/max/top_values já retornados)

Checado nesta ordem — **tipo físico primeiro**, heurísticas de
cardinalidade só como fallback quando o tipo físico não decide sozinho
(a ordem da v1.1 desta spec — puramente por cardinalidade — era
auto-contraditória: `distinct_count < 50` é sempre verdade quando
`distinct_count == 2`, então `boolean` nunca seria alcançável antes de
`categorical`):

| Ordem | Tipo | Critério |
|---|---|---|
| 1 | `date` | tipo físico `DATE` |
| 2 | `timestamp` | tipo físico `DATETIME`/`TIMESTAMP` |
| 3 | `numeric` | tipo físico `INTEGER`/`INT64`/`FLOAT64`/`NUMERIC`/`BIGNUMERIC` |
| 4 | `id` | distinct_pct > 90% |
| 5 | `boolean` | distinct_count = 2 |
| 6 | `email` | STRING, min ou max contém `@` |
| 7 | `date_string` | STRING com padrão `YYYY-MM-DD` em min e max |
| 8 | `numeric_string` | STRING onde min e max são numéricos |
| 9 | `categorical` | distinct_count < 50 |
| 10 | `free_text` | STRING com distinct_pct > 50% |
| 11 | `unknown` | nenhum padrão identificado |

Colunas com tipo físico numérico/data/timestamp nunca passam pelas
heurísticas 4–11 — o tipo já responde a pergunta.

### Quality flag

| Flag | Critério |
|---|---|
| `ok` | completeness ≥ 80% |
| `warning` | completeness 50%–80% |
| `critical` | completeness < 50% |

### Coeficiente de variação
Apenas para INTEGER, FLOAT, NUMERIC: `CV = stddev / avg * 100`

### Registros duplicados estimados
`duplicate_rows = COUNT(*) - APPROX_COUNT_DISTINCT(TO_JSON_STRING(t))`

### Densidade geral
`overall_density = média de completeness_pct de todas as colunas`

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── profiling.py
├── domains/quality/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py
│   ├── sql_builder.py      # Gera SQL dinamicamente
│   └── schemas.py
└── tests/unit/quality/
    ├── test_service.py
    ├── test_sql_builder.py  # Testa geração de SQL sem tocar BQ
    └── test_schemas.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Tabela com 0 linhas | Métricas zeradas, sem erro |
| Coluna com 100% nulos | completeness = 0%, quality_flag = critical |
| Coluna STRUCT/ARRAY | Excluída do profiling, informado no response |
| date_column inexistente | HTTP 400 com lista de colunas de data disponíveis |
| sample_percent < 1 | HTTP 400 — mínimo 1% |
| Timeout > 60s | HTTP 504 com sugestão de reduzir amostragem |

---

## Fora do escopo desta spec

- Comparação histórica entre execuções (fase futura)
- Detecção de PII (Fase 3)
- Validação de constraints de negócio (fase futura)
- Exportação de relatório (fase futura)
