# Spec — Domínio: Freshness com SLA

**Versão:** 1.2 (freshness por tabela em tempo real via client.get_table())
**Status:** Aprovada
**Fase:** 2 — MVP v1
**Última atualização:** 2026-08-11

---

## Objetivo

Monitorar atualização de tabelas BigQuery e classificar status em relação a
janelas de SLA fixas. A região é descoberta automaticamente via metadados do
dataset — nenhum parâmetro de região necessário nos endpoints.

---

## Lógica de classificação de SLA

| Status | Cor | Critério |
|---|---|---|
| `ok` | verde | ≤ 12h |
| `warning_12_24` | amarelo claro | 12h a 24h |
| `warning_24_48` | amarelo | 24h a 48h |
| `warning_48_7d` | laranja | 48h a 7 dias |
| `warning_7d_1m` | vermelho claro | 7 dias a 1 mês |
| `stale` | vermelho | > 1 mês |

---

## Endpoints da API

### GET /api/v1/freshness/{project_id}
Visão consolidada de todos os datasets do projeto.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "evaluated_at": "2026-08-05T10:00:00Z",
  "datasets": [
    {
      "dataset_id": "RAW",
      "location": "US",
      "total_tables": 3,
      "ok": 0,
      "warning_12_24": 0,
      "warning_24_48": 0,
      "warning_48_7d": 0,
      "warning_7d_1m": 0,
      "stale": 3,
      "worst_status": "stale"
    }
  ]
}
```

---

### GET /api/v1/freshness/{project_id}/datasets/{dataset_id}
Freshness detalhado de todas as tabelas de um dataset.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "dataset_id": "RAW",
  "location": "US",
  "evaluated_at": "2026-08-05T10:00:00Z",
  "summary": {
    "total_tables": 3,
    "ok": 0,
    "warning_12_24": 0,
    "warning_24_48": 0,
    "warning_48_7d": 0,
    "warning_7d_1m": 0,
    "stale": 3
  },
  "tables": [
    {
      "table_id": "crm_leads",
      "table_type": "TABLE",
      "last_modified_time": "2024-01-15T00:00:00Z",
      "hours_since_update": 14424.0,
      "sla_status": "stale",
      "size_bytes": 849813,
      "row_count": 10000
    }
  ]
}
```

---

## Query BigQuery

A região é resolvida previamente via `discover_regions()` do core.

### Visão de projeto — `GET /freshness/{project_id}`

Continua lendo de `TABLE_STORAGE` (lag de até 24h, mas uma única query
agregada por região em vez de uma chamada de API por tabela do projeto
inteiro):

```sql
SELECT
  table_schema                                           AS dataset_id,
  table_name                                             AS table_id,
  table_type,
  last_modified_time,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, HOUR)
                                                         AS hours_since_update,
  total_logical_bytes                                    AS size_bytes,
  total_rows                                             AS row_count,
  CASE
    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, HOUR) <= 12
      THEN 'ok'
    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, HOUR) <= 24
      THEN 'warning_12_24'
    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, HOUR) <= 48
      THEN 'warning_24_48'
    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, HOUR) <= 168
      THEN 'warning_48_7d'
    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, HOUR) <= 720
      THEN 'warning_7d_1m'
    ELSE 'stale'
  END                                                    AS sla_status
FROM `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE`
ORDER BY hours_since_update DESC
```
Custo: $0

### Visão de dataset — `GET /freshness/{project_id}/datasets/{dataset_id}`

Lê a lista de tabelas via SQL e `last_modified_time`/`size_bytes`/`row_count`
via `client.get_table()` (tempo real, sem o lag de `TABLE_STORAGE`) — uma
chamada por tabela, em paralelo (`ThreadPoolExecutor`) e cacheada em memória
por 5min (`core/bigquery.py::get_tables_metadata`, compartilhada com o
domínio catalog). `sla_status`/`hours_since_update` são calculados em Python
a partir de `Table.modified`, com a mesma janela de SLA e o mesmo guard para
`modified is None` que a query acima tem para `last_modified_time IS NULL`.

```sql
SELECT table_name AS table_id, table_type
FROM `<project>.region-<region>.INFORMATION_SCHEMA.TABLES`
WHERE table_schema = @dataset_id
```
Custo: $0

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── freshness.py
├── domains/freshness/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py
│   └── schemas.py
└── tests/unit/freshness/
    ├── test_service.py
    └── test_schemas.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Tabela nunca atualizada | `last_modified_time` = `creation_time`, classificada normalmente |
| View | Incluída — reflete última alteração da definição |
| Tabela externa | Incluída — `last_modified_time` pode não refletir dados externos |
| Dataset vazio | `total_tables: 0`, summary zerado |

---

## Fora do escopo desta spec

- SLA configurável por tabela (fase futura)
- Histórico de atualizações dos últimos 30 dias (fase futura)
- Alertas via email/Slack (fase futura)
- Detecção de anomalias de volume (fase futura)
