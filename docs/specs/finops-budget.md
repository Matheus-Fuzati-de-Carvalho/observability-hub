# Spec — Domínio: FinOps — Budget de custo

**Versão:** 1.0
**Status:** Aprovada
**Fase:** 4 — FinOps (segunda frente: budget por dataset/projeto)
**Última atualização:** 2026-08-15

---

## Objetivo

Quatro visões de custo do mês corrente, todas derivadas da mesma fonte
já usada pelo scanner de desperdício — nenhuma integração nova:

1. **Custo por dataset** — quanto cada dataset custou em bytes escaneados.
2. **Top N queries mais caras** — os jobs individuais de maior custo.
3. **Top N gastadores** — humanos e service accounts, por custo total.
4. **Projeção do mês** — custo até agora, média diária, projeção pro
   total do mês.

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
em "custo por dataset" quanto em "top gastadores" (a SA do Hub pode
legitimamente aparecer ali se o usuário rodar muitos scans). Nenhuma
exclusão é aplicada.

---

## Endpoint da API

### GET /api/v1/finops/{project_id}/budget
Sempre relativo ao **mês corrente** (dia 1 até agora, UTC) — não é uma
janela fixa como o scanner de desperdício.

**Parâmetros opcionais:**
- `limit` (query, default `10`, mínimo `1`, máximo `50`) — tamanho de
  `top_queries` e `top_spenders`.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "period_start": "2026-08-01T00:00:00Z",
  "lookback_days": 15,
  "by_dataset": [
    { "dataset_id": "RAW", "cost_usd": 5.68, "billed_bytes": 1000000000000 }
  ],
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
  "top_spenders": [
    {
      "principal_email": "backend-run@observability-hub-dev.iam.gserviceaccount.com",
      "is_service_account": true,
      "cost_usd": 3.20,
      "billed_bytes": 563200000000,
      "job_count": 42
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

## Lógica de agregação

```python
# domains/finops/service.py
def get_budget(
    logging_client: cloud_logging.Client,
    project_id: str,
    limit: int = 10,
) -> BudgetResponse:
    """
    1. month_start = dia 1 do mês corrente, 00:00 UTC. lookback_days =
       dias desde month_start + 1 (a folga de +1 garante que o cutoff
       passado pro Cloud Logging fique ANTES da meia-noite de
       month_start, não depois — ver "Casos de borda").
    2. Busca eventos com repository.list_scan_events(lookback_days) —
       mesma função do scanner de desperdício, reaproveitada.
    3. Descarta evento sem timestamp, anterior a month_start (a folga do
       passo 1 pode trazer eventos do fim do mês anterior) ou com
       total_billed_bytes <= 0 (query sem custo não soma em nenhuma
       agregação, nem conta em job_count de top_spenders).
    4. Por evento: soma total_billed_bytes em by_dataset (uma vez por
       dataset distinto tocado — JOIN entre dois datasets soma nos dois,
       mesma aproximação já documentada no scanner de desperdício pra
       economia de particionamento) e em by_principal (email de quem
       rodou); guarda a linha bruta de CostlyQuery.
    5. by_dataset e top_spenders ordenados por custo desc; top_queries
       ordenado por custo desc, cortado em `limit`.
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
│   └── finops.py          # + GET /finops/{project_id}/budget
├── domains/finops/
│   ├── service.py          # + get_budget()
│   ├── repository.py       # ScanEvent + job_id/principal_email/query_text
│   └── schemas.py          # + DatasetCost, CostlyQuery, TopSpender, CostProjection, BudgetResponse
└── tests/unit/finops/
    ├── test_service.py      # + testes de get_budget
    └── test_repository.py   # + testes de extração de job_id/principal_email/query_text
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Evento com `total_billed_bytes <= 0` | Ignorado em toda agregação — não soma custo nem `job_count` |
| Evento anterior a `month_start` | Ignorado (a folga de `lookback_days = dias + 1` pode trazer alguns) |
| Job de outro projeto referenciando tabela deste | Ignorado — comparação pela tripla completa `(project_id, dataset_id, table_id)` |
| Query com `JOIN` entre datasets | Custo somado em **cada** dataset tocado, não dividido — mesma aproximação do scanner de desperdício |
| Mesmo usuário com múltiplos jobs no mês | Um único registro em `top_spenders`, `job_count` e `billed_bytes` somados |
| Texto de query maior que 2000 caracteres | Truncado com "…" no fim (`repository._QUERY_TEXT_MAX_CHARS`) |
| Mês com mais de 30 dias corridos até agora (dia 31) | `warning` avisa sobre a retenção padrão de 30 dias do Cloud Logging — o início do mês pode estar faltando |
| Nenhum evento de job no projeto | `warning` populado (mesmo texto/causas de lineage/access/scanner de desperdício), todas as listas vazias |
| `limit` fora do intervalo 1–50 | HTTP 422 (validação do `Query(ge=1, le=50)`) |

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
- **Atribuição proporcional de custo em JOINs multi-dataset** — custo
  soma inteiro em cada dataset tocado, não dividido pela proporção real
  de bytes por tabela dentro do job (dado que não está disponível no
  audit log).
