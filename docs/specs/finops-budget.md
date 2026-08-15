# Spec — Domínio: FinOps — Budget de custo

**Versão:** 1.1
**Status:** Aprovada
**Fase:** 4 — FinOps (segunda frente: budget por dataset/projeto)
**Última atualização:** 2026-08-15

---

## Objetivo

Três visões de custo do mês corrente, todas derivadas da mesma fonte já
usada pelo scanner de desperdício — nenhuma integração nova:

1. **Custo agrupado, agrupamento configurável** — Tabela | Usuário | Dia
   | Mês | Ano (`group_by`). Substituiu a v1.0, que só tinha "custo por
   dataset" fixo — ver "Agrupamento configurável" abaixo.
2. **Top N queries mais caras** — os jobs individuais de maior custo.
3. **Projeção do mês** — custo até agora, média diária, projeção pro
   total do mês.

*(A v1.0 também tinha "top N gastadores" como visão separada — removida
na v1.1: `group_by=user` cobre o mesmo caso, sem duplicar lógica de
agregação.)*

---

## Fonte de dados — por que não precisa de nada novo configurado

A opção óbvia seria **BigQuery Billing Export** (Cloud Billing exportado
pra uma tabela BigQuery) — mas ela quebra custo só por **projeto + SKU**,
nunca por dataset/tabela individual, então não resolveria "quanto esse
dataset custou" mesmo se configurada. A granularidade que este domínio
precisa só existe nos **audit logs de jobs do BigQuery** (Cloud Logging,
`jobservice.jobcompleted`) — mesma fonte que `scan_unused_tables`/
`scan_partition_candidates` já leem, com dois campos que nenhuma outra
função deste domínio usava antes: `principalEmail` (quem rodou) e
`jobConfiguration.query.query` (o texto da query, truncado em 2000
caracteres — `repository._QUERY_TEXT_MAX_CHARS` — pra não inflar a
resposta de top queries).

Nenhuma API nova, nenhuma role de IAM nova — `roles/logging.privateLogViewer`
já é exigido no checklist de `docs/onboarding-cliente.md` pra lineage/
access/scanner de desperdício, e cobre budget também.

### É uma estimativa, não a fatura real

`totalBilledBytes × settings.bigquery_price_usd_per_tib` é a mesma conta
que o BigQuery mostra como prévia de custo antes de rodar uma query —
precisa **se o projeto usa cobrança on-demand** (por bytes escaneados,
o padrão, e a mesma premissa que já vale pra `domains/quality` e pro
scanner de desperdício). Se o projeto usa **flat-rate/Editions** (slots
reservados, custo fixo por capacidade), essa estimativa **não reflete o
gasto real** — nesse modelo o custo é por hora de slot, não por byte
escaneado. Isso não é uma limitação nova desta feature especificamente:
é a mesma premissa on-demand que já está embutida em toda estimativa de
custo do Hub. Documentado aqui porque budget é onde um número errado
mais provavelmente vira uma decisão financeira.

### Diferente do mapa de acesso: a SA do próprio Hub CONTA aqui

`domains/access` exclui a SA de runtime do Hub da agregação porque ali a
pergunta é "quem consome essa tabela de fora" (rodar profiling pela UI
não é um consumidor externo real). Budget pergunta outra coisa: "quanto
está sendo gasto de verdade nesse projeto" — e profiling/PII rodados
pela UI do Hub **custam dinheiro de verdade**, então devem contar tanto
em `group_by=table` quanto em `group_by=user` (a SA do Hub pode
legitimamente aparecer ali se o usuário rodar muitos scans). Nenhuma
exclusão é aplicada por identidade do principal.

### Bug real corrigido: regiões fantasma no agrupamento por tabela

**Sintoma observado em dev:** `groups` (então `by_dataset`) trazia
entradas como `region-US` com custo residual (~$0.07) sem corresponder
a nenhum dataset real do projeto.

**Causa raiz** (investigada com `gcloud logging read` + replay da lógica
de agregação contra ~5000 eventos reais de `observability-hub-dev`,
agosto/2026): `discover_regions()` / `repository.list_all_table_refs()` /
`repository.get_date_like_columns()` — usadas por `catalog`, `freshness`
e pelo próprio `finops` para descoberta de metadados a custo ~zero —
rodam queries region-qualificadas
(`` `project.region-X.INFORMATION_SCHEMA.*` ``). O audit log dessas
queries registra `referencedTables[].datasetId="region-US"` (ou
`region-EU`, etc.) e `tableId="INFORMATION_SCHEMA.SCHEMATA"` (ou
`.TABLES`, `.TABLE_STORAGE`...) — indistinguível, à primeira vista, de
uma tabela real de cliente chamada `region-US`. Na amostra investigada,
**4989 de 5000 jobs (99,8%)** eram esse ruído, todos disparados pela SA
de runtime do Hub — deixando só ~11 jobs de atividade real.

**Fix:** `repository._parse_table_ref()` descarta qualquer referência
cujo `table_id` comece com `INFORMATION_SCHEMA.`, na origem — benefício
automático para todas as funções deste domínio (`scan_unused_tables`,
`scan_partition_candidates`, `get_budget`), não só budget.
`service.get_budget()` reforça isso pulando o evento inteiro (não só a
atribuição de dataset, mas também `top_queries`) quando, após o filtro,
`real_tables` fica vazio — cobre tanto "só referenciava
INFORMATION_SCHEMA" quanto "só referenciava tabela de outro projeto".
Ver teste `test_parse_table_ref_filters_information_schema_probes`
(`tests/unit/finops/test_repository.py`) e
`test_get_budget_skips_events_with_no_real_table_information_schema_only`
(`tests/unit/finops/test_service.py`).

Esse era o bug real por trás de um relato inicial tecnicamente impreciso
(hipótese de iteração sobre `BQ_REGIONS` chamando
`INFORMATION_SCHEMA.JOBS`, o que este domínio nunca fez — `get_budget`
sempre leu só Cloud Logging). A causa raiz confirmada foi outra, mas o
sintoma reportado ($0.07 fantasma) era real.

---

## Endpoint da API

### GET /api/v1/finops/{project_id}/budget
Sempre relativo ao **mês corrente** (dia 1 até agora, UTC) — não é uma
janela fixa como o scanner de desperdício.

**Parâmetros opcionais:**
- `group_by` (query, default `table`) — um de `table`, `user`, `day`,
  `month`, `year`. Ver "Agrupamento configurável".
- `limit` (query, default `10`, mínimo `1`, máximo `50`) — tamanho de
  `top_queries`.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "period_start": "2026-08-01T00:00:00Z",
  "lookback_days": 15,
  "group_by": "table",
  "groups": [
    {
      "key": "observability-hub-dev.RAW.ga4_events",
      "cost_usd": 5.68,
      "billed_bytes": 1000000000000,
      "job_count": 12
    }
  ],
  "total_cost_usd": 8.88,
  "top_queries": [
    {
      "job_id": "bqjob_...",
      "principal_email": "ana@dp6.com.br",
      "executed_at": "2026-08-14T14:33:05Z",
      "billed_bytes": 1000000000000,
      "cost_usd": 5.68,
      "tables": ["observability-hub-dev.RAW.ga4_events"],
      "query_text": "SELECT ..."
    }
  ],
  "projection": {
    "days_elapsed": 15,
    "days_in_month": 31,
    "cost_so_far_usd": 8.88,
    "daily_average_usd": 0.592,
    "projected_month_total_usd": 18.35
  },
  "warning": null
}
```

---

## Agrupamento configurável (`group_by`)

Uma ou mais chaves por evento, calculadas em `service._group_keys()`:

| `group_by` | Chave | Cardinalidade por evento |
|---|---|---|
| `table` (default) | `project.dataset.table` de cada tabela real referenciada | 1 por tabela tocada — fan-out em `JOIN`, mesma aproximação de "custo por dataset" da v1.0 |
| `user` | `principal_email` | 1 |
| `day` | `timestamp.date().isoformat()` | 1 |
| `month` | `timestamp.strftime('%Y-%m')` | 1 |
| `year` | `str(timestamp.year)` | 1 |

Só `group_by=table` tem fan-out (uma query com `JOIN` entre tabelas soma
o custo inteiro em cada tabela tocada, não dividido pela proporção real
de bytes — mesma limitação da v1.0, ver "Fora do escopo"); as demais
dimensões são 1:1 por evento.

---

## Lógica de agregação

```python
# domains/finops/service.py
def get_budget(
    logging_client: cloud_logging.Client,
    project_id: str,
    group_by: BudgetGroupBy = BudgetGroupBy.TABLE,
    limit: int = 10,
) -> BudgetResponse:
    """
    1. month_start = dia 1 do mês corrente, 00:00 UTC. lookback_days =
       dias desde month_start + 1 (a folga de +1 garante que o cutoff
       passado pro Cloud Logging fique ANTES da meia-noite de
       month_start, não depois — ver "Casos de borda").
    2. Busca eventos com repository.list_scan_events(lookback_days) —
       mesma função do scanner de desperdício, reaproveitada.
       referenced_tables já vem sem entradas INFORMATION_SCHEMA (filtro
       na origem, repository._parse_table_ref).
    3. Descarta evento sem timestamp, anterior a month_start (a folga do
       passo 1 pode trazer eventos do fim do mês anterior),
       com total_billed_bytes <= 0, ou cujo real_tables (tabelas
       referenciadas que pertencem a este project_id) fique vazio depois
       do filtro — ver "Bug real corrigido: regiões fantasma".
    4. Por evento: soma total_billed_bytes/job_count em uma ou mais
       chaves via _group_keys(group_by, event, real_tables); guarda a
       linha bruta de CostlyQuery.
    5. groups ordenado por custo desc; top_queries ordenado por custo
       desc, cortado em `limit`.
    6. Projeção: daily_average = custo_total_do_mês_até_agora /
       lookback_days (dias corridos do mês, não só dias com atividade —
       um mês com poucos dias ativos não deve inflar a média).
       days_in_month via calendar.monthrange(). projected_total =
       daily_average × days_in_month.
    """
```

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── finops.py          # + GET /finops/{project_id}/budget?group_by=...
├── domains/finops/
│   ├── service.py          # + get_budget(), _group_keys()
│   ├── repository.py       # ScanEvent + job_id/principal_email/query_text; _parse_table_ref filtra INFORMATION_SCHEMA
│   └── schemas.py          # + BudgetGroupBy, CostGroup, CostlyQuery, CostProjection, BudgetResponse
└── tests/unit/finops/
    ├── test_service.py      # + testes de get_budget por dimensão de group_by
    └── test_repository.py   # + testes de extração de job_id/principal_email/query_text + filtro INFORMATION_SCHEMA
```

Frontend (`apps/frontend/src/features/finops/BudgetPage.tsx`): duas
abas via `Tabs` do shadcn/ui — "Custo por agrupamento" (seletor de
`group_by` em pill buttons, tabela ordenável, total no rodapé via
`TableFooter`) e "Queries mais caras" (tabela ordenável por custo/bytes/
data; coluna "Tabelas" como badges; texto da query oculto por padrão,
com toggle "Ver query"/"Ocultar query" por linha que expande um bloco
`SqlPreview` — mesmo componente compartilhado do preview de SQL do
profiling — abaixo da linha, evitando a sobreposição visual que a v1.0
tinha com o texto da query inline na célula).

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Referência a `INFORMATION_SCHEMA.*` (probes de região do próprio Hub) | Filtrada na origem (`repository._parse_table_ref`) — nunca vira dataset/tabela fantasma em nenhum `group_by` |
| Evento cujas `referenced_tables`, após o filtro acima, não sobra nenhuma do `project_id` (só probe ou só tabela de outro projeto) | Evento inteiro pulado — não entra em `groups` nem em `top_queries` |
| Evento com `total_billed_bytes <= 0` | Ignorado em toda agregação — não soma custo nem `job_count` |
| Evento anterior a `month_start` | Ignorado (a folga de `lookback_days = dias + 1` pode trazer alguns) |
| Query com `JOIN` entre tabelas (`group_by=table`) | Custo somado em **cada** tabela tocada, não dividido — mesma aproximação do scanner de desperdício |
| Mesmo usuário com múltiplos jobs no mês (`group_by=user`) | Um único `CostGroup`, `job_count` e `billed_bytes` somados |
| Texto de query maior que 2000 caracteres | Truncado com "…" no fim (`repository._QUERY_TEXT_MAX_CHARS`) |
| Mês com mais de 30 dias corridos até agora (dia 31) | `warning` avisa sobre a retenção padrão de 30 dias do Cloud Logging — o início do mês pode estar faltando |
| Nenhum evento de job no projeto | `warning` populado (mesmo texto/causas de lineage/access/scanner de desperdício), `groups`/`top_queries` vazios |
| `limit` fora do intervalo 1–50 | HTTP 422 (validação do `Query(ge=1, le=50)`) |
| `group_by` fora do enum | HTTP 422 (validação do `Query` com `BudgetGroupBy`) |

---

## Fora do escopo desta spec

- **Terceira frente de FinOps** (otimizações sugeridas de clustering/tipo
  de coluna) — fica pra depois.
- **Custo real exato** via BigQuery Billing Export — decisão consciente
  de não usar, ver "Fonte de dados" (não teria a granularidade de
  dataset que este domínio precisa, mesmo se configurado).
- **Suporte a projetos flat-rate/Editions** — a estimativa assume
  cobrança on-demand; num projeto flat-rate os números aqui não
  refletem o gasto real (mesma premissa já embutida em `domains/quality`
  e no scanner de desperdício).
- **Histórico entre meses** — só o mês corrente; sem persistência,
  cada consulta reflete só a janela de audit logs disponível agora.
- **Atribuição proporcional de custo em JOINs multi-tabela** — custo
  soma inteiro em cada tabela tocada (`group_by=table`), não dividido
  pela proporção real de bytes por tabela dentro do job (dado que não
  está disponível no audit log).
- **Combinar duas dimensões de `group_by` na mesma resposta** (ex:
  usuário × dia) — só uma dimensão por chamada; cruzar dimensões fica
  pra uma iteração futura se houver demanda concreta.
