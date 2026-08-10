# Spec — Domínio: Profiling (quality)

**Status:** Aprovada
**Fase:** 2 — MVP v1
**Última atualização:** 2026-08-05

---

## Objetivo

Análise estatística configurável de qualquer tabela BigQuery, coluna a coluna,
com controles de amostragem, filtro temporal e estimativa de custo antes da
execução. Substitui queries manuais de profiling no processo de discovery e
análise exploratória de qualidade de dados.

---

## Fluxo de uso

```
1. Usuário abre modal "Analisar" em uma tabela do catálogo
2. Configura parâmetros (amostragem, método, coluna de data, janela)
3. Clica em "Estimar Custo" → dry run retorna volume e custo estimado
4. Revisa SQL gerado na interface
5. Clica em "Executar Profile" → retorna métricas por coluna e por tabela
6. Opcional: drill down em "Distribuição de nulos ao longo do tempo"
```

---

## Parâmetros de configuração

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `sample_percent` | float | 100 | % de amostragem via TABLESAMPLE SYSTEM |
| `uniqueness_method` | enum | `approx` | `approx` (HLL) ou `exact` (COUNT DISTINCT) |
| `date_column` | string | null | Coluna de data para filtro temporal |
| `date_window_days` | int | null | Janela temporal em dias (D-X dias) |

---

## Endpoints da API

### POST /api/v1/profiling/{project_id}/{dataset_id}/{table_id}/estimate
Dry run — retorna bytes estimados e custo sem executar a query real.

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
  "sql": "SELECT COUNT(*) AS _total_sampled_rows, COUNT(`lead_id`) AS lead_id__count_filled, APPROX_COUNT_DISTINCT(`lead_id`) AS lead_id__approx_distinct ... FROM `cliente-x-prod.RAW.crm_leads_mock` TABLESAMPLE SYSTEM (10.0 PERCENT) WHERE `date` >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)"
}
```

---

### POST /api/v1/profiling/{project_id}/{dataset_id}/{table_id}/run
Executa o profiling e retorna métricas completas.

**Body:** mesmo schema do `/estimate`

**Response 200:**
```json
{
  "project_id": "cliente-x-prod",
  "dataset_id": "RAW",
  "table_id": "crm_leads_mock",
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
      "column_name": "lead_id",
      "data_type": "STRING",
      "is_nullable": true,
      "completeness_pct": 100.0,
      "null_count": 0,
      "distinct_count": 9526,
      "distinct_pct": 95.26,
      "min_value": "ld-200000",
      "max_value": "ld-209999",
      "top_values": null,
      "inferred_logical_type": "id",
      "coefficient_of_variation": null,
      "quality_flag": "ok"
    },
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

### Query de profiling principal

Gerada dinamicamente com base nas colunas da tabela:

```sql
SELECT
  COUNT(*) AS _total_sampled_rows,

  -- Para cada coluna:
  COUNT(`{col}`)                    AS {col}__count_filled,
  -- Se approx:
  APPROX_COUNT_DISTINCT(`{col}`)    AS {col}__approx_distinct,
  -- Se exact:
  COUNT(DISTINCT `{col}`)           AS {col}__exact_distinct,
  MIN(`{col}`)                      AS {col}__min,
  MAX(`{col}`)                      AS {col}__max,
  -- Se numérico:
  AVG(CAST(`{col}` AS FLOAT64))     AS {col}__avg,
  STDDEV(CAST(`{col}` AS FLOAT64))  AS {col}__stddev

FROM `{project}.{dataset}.{table}`
  TABLESAMPLE SYSTEM ({sample_percent} PERCENT)   -- se sample_percent < 100
WHERE `{date_column}` >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
  -- omitido se date_column não informado
```

### Top N valores

Executada separadamente, apenas para colunas com `distinct_count < 50`:

```sql
SELECT `{col}` AS value, COUNT(*) AS count
FROM `{project}.{dataset}.{table}`
  TABLESAMPLE SYSTEM ({sample_percent} PERCENT)
WHERE `{date_column}` >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
GROUP BY 1
ORDER BY count DESC
LIMIT 10
```

---

## Regras de negócio das métricas

### Tipo lógico inferido (sem custo extra — usa min/max/top_values)

| Tipo inferido | Critério |
|---|---|
| `id` | distinct_pct > 90% |
| `categorical` | distinct_count < 50 |
| `email` | min ou max contém `@` |
| `date_string` | STRING com padrão `YYYY-MM-DD` |
| `numeric_string` | STRING onde min e max são numéricos |
| `boolean` | distinct_count = 2 |
| `free_text` | STRING com distinct_pct > 50% e sem padrão |
| `unknown` | nenhum padrão identificado |

### Quality flag por coluna

| Flag | Critério |
|---|---|
| `ok` | completeness ≥ 80% |
| `warning` | completeness entre 50% e 80% |
| `critical` | completeness < 50% |

### Coeficiente de variação

Calculado apenas para colunas numéricas (INTEGER, FLOAT, NUMERIC):
`CV = stddev / avg * 100`

### Registros duplicados estimados

`duplicate_rows = total_rows - distinct_count(concat de todas as colunas)`
Usando APPROX_COUNT_DISTINCT para performance.

### Densidade geral da tabela

`overall_density = média de completeness_pct de todas as colunas`

---

## Estrutura de arquivos a criar

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── profiling.py
├── domains/quality/
│   ├── __init__.py
│   ├── service.py          # Orquestra estimate, run e null-distribution
│   ├── repository.py       # Executa queries BQ e dry run
│   ├── sql_builder.py      # Gera SQL dinamicamente por tabela/colunas
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
| Tabela com 0 linhas | Retorna métricas zeradas, sem erro |
| Coluna com 100% nulos | completeness = 0%, quality_flag = critical |
| Coluna STRUCT/ARRAY | Excluída do profiling com nota no response |
| date_column inexistente | HTTP 400 com lista de colunas de data disponíveis |
| sample_percent = 0 | HTTP 400 — mínimo 1% |
| Timeout de query (> 60s) | HTTP 504 com sugestão de reduzir amostragem |

---

## Fora do escopo desta spec

- Comparação histórica entre execuções (fase futura)
- Detecção de PII (Fase 3 — usa lógica diferente)
- Validação de constraints de negócio (fase futura)
- Exportação de relatório de profiling (fase futura)
