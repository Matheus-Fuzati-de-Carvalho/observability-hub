# Spec — Domínio: FinOps — Scanner de desperdício

**Versão:** 1.0
**Status:** Aprovada
**Fase:** 4 — FinOps (primeira frente: scanner de desperdício)
**Última atualização:** 2026-08-15

---

## Objetivo

Duas checagens independentes de desperdício num projeto BigQuery:

1. **Tabelas sem uso** — nunca lidas (ou não lidas há N dias) nos audit
   logs, com estimativa de custo de storage evitável.
2. **Candidatas a particionamento** — tabelas grandes, sem partição,
   com uma coluna `DATE`/`DATETIME`/`TIMESTAMP` candidata, com uma
   estimativa (deliberadamente conservadora, nunca um número único de
   falsa precisão) de quanto poderia ser economizado particionando.

Este é o primeiro dos três sub-domínios de FinOps do roadmap (`docs/prd.md`,
Fase 4) — budget/custo por dataset e otimizações sugeridas ficam pra
depois, não fazem parte desta spec.

---

## Fonte de dados

Combina duas fontes já usadas por outros domínios:

- **Cloud Logging** (audit logs de jobs BigQuery, `jobservice.jobcompleted`,
  custo $0) — mesmo formato legado `AuditData`/`jobCompletedEvent` de
  `domains/lineage`/`domains/access`. Aqui só interessa leitura
  (`referencedTables`) e um campo novo que nenhum outro domínio lê ainda:
  `jobStatistics.totalBilledBytes` — bytes realmente cobrados por aquele
  job, usado pra ancorar a estimativa de economia de particionamento em
  custo **observado**, não numa suposição do zero.
- **BigQuery `INFORMATION_SCHEMA`** (enumeração de tabelas, custo $0) +
  **`client.get_table()`** (`core/bigquery.py::get_tables_metadata`,
  REST, cacheado 5min, já usado por catalog/freshness — reaproveitado
  direto por ser `core/`, não um domínio) pra tamanho, contagem de
  linhas, `last_modified_time` e se a tabela já é particionada
  (`time_partitioning`/`range_partitioning`).

`domains/finops/repository.py` duplica o parsing de audit log (não
importa de `lineage`/`access` — nenhum domínio deste projeto importa de
outro).

---

## Endpoints da API

### GET /api/v1/finops/{project_id}/unused-tables
Tabelas sem leitura conhecida na janela pedida.

**Parâmetros opcionais:**
- `min_days_unused` (query, default `30`) — `30`, `60` ou `90`.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "min_days_unused": 30,
  "lookback_days": 90,
  "tables": [
    {
      "dataset_id": "RAW",
      "table_id": "old_import_2024",
      "size_bytes": 5368709120,
      "size_human": "5.37 GB",
      "last_accessed_at": null,
      "days_since_last_access": null,
      "estimated_monthly_storage_cost_usd": 0.0537
    }
  ],
  "warning": null
}
```

`last_accessed_at`/`days_since_last_access` nulos = tabela não aparece
em nenhum job de leitura nos 90 dias consultados (pode nunca ter sido
lida, ou ter sido lida antes disso — os dois casos são indistinguíveis
pela mesma razão de sempre: a janela de audit logs é finita).

---

### GET /api/v1/finops/{project_id}/partition-candidates
Tabelas grandes, não particionadas, com coluna candidata a chave de
partição.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "lookback_days": 30,
  "candidates": [
    {
      "dataset_id": "RAW",
      "table_id": "ga4_events_flat",
      "size_bytes": 10737418240,
      "size_human": "10.74 GB",
      "row_count": 42000000,
      "candidate_partition_columns": ["event_date"],
      "observed_billed_bytes_30d": 1099511627776,
      "observed_cost_usd_30d": 6.25,
      "estimated_savings_usd_conservative": 1.875,
      "estimated_savings_usd_optimistic": 4.375,
      "savings_disclaimer": "Estimativa especulativa baseada no custo de scan REAL observado nos últimos 30 dias — não confirma que as queries filtram pela coluna de data candidata..."
    }
  ],
  "warning": null
}
```

`estimated_savings_usd_*` e `savings_disclaimer` só vêm preenchidos
quando `observed_billed_bytes_30d > 0` — sem custo real observado, a
tabela ainda aparece como candidata (tamanho/colunas), mas sem nenhuma
estimativa em R$/US$ (ver "Estimativa de economia — desenho").

---

## Estimativa de economia — desenho

Decisão de design discutida explicitamente com o usuário: **nunca
fabricar um número de aparência precisa sobre uma suposição não
verificada** — o risco de superestimar e gerar frustração depois pesa
mais que a conveniência de mostrar "um número só".

### Tabelas sem uso
Estimativa **factual**, não especulativa: `size_bytes` × preço de
storage por GB/mês (`settings.bigquery_storage_price_usd_per_gb_month_active`
ou `..._long_term`, conforme `last_modified_time` — BigQuery já rebaixa
a tarifa sozinho pra tabelas sem modificação há 90+ dias). Isso é custo
real de storage que já está sendo pago, não uma projeção.

### Candidatas a particionamento
Aqui não dá pra saber se as queries reais filtram pela coluna de data
candidata sem rodar algo mais caro (analisar o texto de cada query) —
fora de escopo desta v1. Em vez de assumir uma redução do zero, o
desenho é:

1. Soma `totalBilledBytes` de todo job real que leu a tabela nos
   últimos 30 dias — **fato observado**, convertido em US$ pelo mesmo
   preço on-demand de `domains/quality` (`settings.bigquery_price_usd_per_tib`).
2. Só oferece uma estimativa de economia se **(a)** a tabela tem coluna
   candidata a partição **e** **(b)** houve custo real observado — sem
   os dois, mostra a tabela como candidata sem nenhum número de
   economia.
3. Quando oferece, mostra uma **faixa** (30%–70% de redução sobre o
   custo observado), não um valor único — o formato de faixa já
   comunica a incerteza, em vez de esconder atrás de uma falsa precisão.
4. Sempre acompanhada de `savings_disclaimer` explícito.

**Limitação assumida conscientemente**: se a query faz `JOIN` com outra
tabela grande, `totalBilledBytes` é o custo da query inteira, não
isolado só nesta tabela — não há tentativa de dividir a proporção por
tabela dentro de um job (dado que não está disponível no audit log).

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── finops.py
├── core/
│   ├── bigquery.py         # get_tables_metadata() — reaproveitado, não duplicado (é core/)
│   └── config.py           # bigquery_storage_price_usd_per_gb_month_{active,long_term}
├── domains/finops/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py       # list_scan_events(), list_all_table_refs(), get_date_like_columns()
│   └── schemas.py
└── tests/unit/finops/
    ├── test_service.py
    └── test_repository.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| `min_days_unused` = 60 ou 90 | `warning` informa a limitação de retenção padrão de 30 dias dos audit logs (ver abaixo) |
| Tabela nunca aparece em nenhum job de leitura | `last_accessed_at`/`days_since_last_access` nulos, sempre incluída (qualquer que seja `min_days_unused`) |
| Tabela acessada exatamente há `min_days_unused` dias | Incluída (`>=`, não `>` — "sem uso há pelo menos N dias") |
| Job de outro projeto referenciando a tabela | Ignorado — comparação sempre pela tripla completa `(project_id, dataset_id, table_id)` |
| Tabela some entre a listagem e o fetch de metadata (race) | Não aparece no resultado, sem erro |
| Tabela já particionada | Nunca aparece em `partition-candidates` |
| Tabela abaixo do limite de tamanho (1 GB) | Nunca aparece em `partition-candidates` — pequena demais pra valer o aviso |
| Tabela grande, não particionada, sem coluna DATE/DATETIME/TIMESTAMP | Não aparece — sem coluna candidata, sugestão não é viável |
| Candidata sem custo observado nos últimos 30 dias | Aparece sem `estimated_savings_usd_*`/`savings_disclaimer` (ambos `null`) |
| Nenhum evento de job no projeto | `warning` populado (mesmo texto/causas de lineage/access) |

**Retenção padrão do Cloud Logging**: Data Access audit logs retêm 30
dias por padrão, salvo bucket/sink customizado. `unused-tables` sempre
busca 90 dias de logs (`_UNUSED_TABLES_LOOKBACK_DAYS`), mas se a
retenção real do projeto for a padrão, tudo além de 30 dias atrás
simplesmente não existe mais pra consultar — uma tabela acessada há 45
dias apareceria como "sem uso há 60+ dias" não porque não foi usada, mas
porque o log expirou. Por isso o aviso é automático sempre que
`min_days_unused > 30`.

---

## Fora do escopo desta spec

- Budget por dataset/projeto (custo mensal, top queries caras, top
  usuários por gasto, projeção do mês) — próxima frente de FinOps.
- Otimizações sugeridas além de particionamento (clustering, tipo de
  coluna) — próxima frente de FinOps.
- Análise do texto da query pra confirmar se ela de fato filtra pela
  coluna de data candidata — é isso que tornaria a estimativa de
  economia de particionamento precisa em vez de uma faixa; não
  implementado nesta v1.
- Exclusão automática de tabelas (a funcionalidade só relata, nunca
  apaga/modifica — mesma restrição de escopo somente-leitura de todo o
  Hub, `docs/prd.md`, "Fora do escopo").
- Deletar/arquivar tabelas sem uso — só relata, decisão fica com o
  usuário.
