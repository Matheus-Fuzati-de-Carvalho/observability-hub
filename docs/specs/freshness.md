# Spec — Domínio: Freshness com SLA

**Status:** Aprovada
**Fase:** 2 — MVP v1
**Última atualização:** 2026-08-05

---

## Objetivo

Monitorar a atualização de tabelas BigQuery e classificar seu status em relação
a janelas de SLA configuráveis — identificando tabelas dentro do prazo, em
alerta ou violando o SLA, incluindo tabelas que pararam de atualizar
silenciosamente.

Fonte exclusiva: metadados do `INFORMATION_SCHEMA` — **custo $0**.

---

## Lógica de classificação de SLA

Baseada no tempo decorrido desde `last_modified_time`:

| Status | Cor | Critério |
|---|---|---|
| `ok` | verde | última atualização ≤ 12h |
| `warning_12_24` | amarelo claro | entre 12h e 24h |
| `warning_24_48` | amarelo | entre 24h e 48h |
| `warning_48_7d` | laranja | entre 48h e 7 dias |
| `warning_7d_1m` | vermelho claro | entre 7 dias e 1 mês |
| `stale` | vermelho | última atualização > 1 mês |

As janelas são fixas no MVP — configuração por tabela entra em fase futura.

---

## Endpoints da API

### GET /api/v1/freshness/{project_id}/datasets/{dataset_id}
Retorna status de freshness de todas as tabelas de um dataset.

**Parâmetros:**
- `project_id` (path)
- `dataset_id` (path)
- `region` (query, default: `us-central1`)

**Response 200:**
```json
{
  "project_id": "cliente-x-prod",
  "dataset_id": "RAW",
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
      "table_id": "crm_leads_mock",
      "table_type": "TABLE",
      "last_modified_time": "2026-06-08T18:27:49Z",
      "hours_since_update": 1271.5,
      "sla_status": "stale",
      "size_bytes": 849813,
      "row_count": 10000
    }
  ]
}
```

---

### GET /api/v1/freshness/{project_id}
Retorna visão consolidada de freshness de todos os datasets do projeto.

**Response 200:**
```json
{
  "project_id": "cliente-x-prod",
  "evaluated_at": "2026-08-05T10:00:00Z",
  "datasets": [
    {
      "dataset_id": "RAW",
      "total_tables": 3,
      "ok": 0,
      "stale": 3,
      "worst_status": "stale"
    }
  ]
}
```

---

## Query BigQuery

```sql
SELECT
  table_schema                                        AS dataset_id,
  table_name                                          AS table_id,
  table_type,
  last_modified_time,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, HOUR)
                                                      AS hours_since_update,
  total_logical_bytes                                 AS size_bytes,
  total_rows                                          AS row_count,
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
  END                                                 AS sla_status
FROM `<project>.region-<region>.INFORMATION_SCHEMA.TABLE_STORAGE`
WHERE table_schema = @dataset_id   -- omitir para visão do projeto inteiro
ORDER BY hours_since_update DESC
```
Custo: $0

---

## Estrutura de arquivos a criar

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
| Tabela nunca atualizada (criada mas vazia) | `last_modified_time` = `creation_time`, classificada normalmente |
| View | Incluída — `last_modified_time` reflete última alteração da definição da view |
| Tabela externa | Incluída — `last_modified_time` pode não refletir atualização dos dados externos |
| Dataset vazio | `total_tables: 0`, summary zerado |

---

## Fora do escopo desta spec

- SLA configurável por tabela (fase futura)
- Histórico de atualizações dos últimos 30 dias (fase futura)
- Alertas via email/Slack (fase futura)
- Detecção de anomalias de volume (fase futura)
