# Spec — Domínio: FinOps — Sugestão de tipo de coluna

**Versão:** 1.1
**Status:** Aprovada
**Fase:** 4 — FinOps (terceira frente: otimizações sugeridas)
**Última atualização:** 2026-08-17

---

## Objetivo

Terceira e última frente do roadmap de FinOps (`docs/prd.md`, 4.3 —
"otimizações sugeridas"). Escopo desta v1: **só sugestão de tipo de
coluna** — colunas `STRING` cujos valores amostrados são compatíveis com
um tipo mais estreito (`INT64`, `FLOAT64`, `BOOL`, `DATE`, `DATETIME`,
`TIMESTAMP`), com estimativa de economia de storage se a coluna fosse
recriada com o tipo sugerido. Clustering fica pra uma iteração futura —
ver "Fora do escopo".

Diferente das outras duas frentes de FinOps (scanner de desperdício e
budget), que são 100% metadado/audit-log e custam **$0** pra rodar, esta
precisa amostrar dado real via `TABLESAMPLE` — mesmo mecanismo (e mesmo
custo real) que os domínios `pii`/`quality` já usam. Por isso o desenho é
diferente dos outros dois scanners de FinOps: em vez de carregar sozinho
ao abrir a tela, exige um clique explícito em "Estimar custo" e depois
"Escanear" — mesma disciplina de nunca cobrar do usuário sem ele decidir
antes, olhando pro número.

---

## Escopo de execução (v1.1)

Rodar em **todas** as tabelas de um projeto produtivo é inviável — um
projeto real pode ter centenas ou milhares de tabelas, e cada uma custa
uma query `TABLESAMPLE` de verdade. A partir da v1.1, `estimate` e `run`
aceitam um escopo explícito de tabelas (`ColumnTypeScanRequest.tables`,
lista de `"dataset_id.table_id"`); `None`/lista vazia mantém o
comportamento antigo (projeto inteiro) só como capacidade da API — o
frontend **sempre** manda um escopo explícito nas duas telas onde a
feature aparece (ver "Onde a feature aparece" abaixo).

Com escopo explícito, `_resolve_eligible_tables` pula
`repository.list_all_table_refs` inteiramente — não enumera o projeto
todo pra depois filtrar, resolve region/`is_view`/colunas STRING só das
tabelas pedidas. Reduz tanto o tempo de resposta quanto o número de
chamadas `INFORMATION_SCHEMA` num projeto grande.

### Onde a feature aparece

1. **Aba "Tipos de coluna" em `/finops`** (projeto inteiro, com
   seletor) — lista de datasets com checkbox; marcar um dataset expande
   a lista de tabelas dele (via os mesmos endpoints do catálogo,
   `GET /catalog/{project}/datasets` e
   `GET /catalog/{project}/datasets/{dataset}/tables` — grátis,
   reaproveitados, nenhum endpoint novo) com todas as tabelas
   pré-marcadas; usuário pode desmarcar tabelas individuais pra refinar.
   Botões "Estimar custo"/"Escanear" ficam desabilitados até pelo menos
   uma tabela estar selecionada.
2. **Aba nova no modal de profiling** (por tabela, mesmo lugar de PII)
   — escopo implícito de uma tabela só (`tables: ["{dataset}.{tabela}"]`),
   sem seletor, mesmo fluxo estimar→escanear da aba de projeto.

---

## Como funciona a detecção de tipo

Por coluna `STRING` elegível, uma única query agregada testa, em ordem
de prioridade (primeiro tipo com 100% de match no não-nulo amostrado
vence — nunca sugere mais de um tipo por coluna):

1. `INT64` — `SAFE_CAST(col AS INT64) IS NOT NULL`
2. `FLOAT64` — só chega aqui se `INT64` não bateu 100% (todo INT64 válido
   também é `FLOAT64` válido — checar `INT64` primeiro evita sugerir o
   tipo mais largo quando o mais estreito já serve)
3. `BOOL` — `SAFE_CAST(col AS BOOL) IS NOT NULL` (BigQuery só aceita
   `"true"`/`"false"`, case-insensitive — não `"0"`/`"1"`, que já teriam
   batido em `INT64` antes de chegar aqui)
4. `DATE`, depois `DATETIME`, depois `TIMESTAMP` — `SAFE_CAST(col AS X)
   IS NOT NULL`

`SAFE_CAST` roda inteiramente em SQL, retorna `NULL` em vez de erro
quando o valor não é compatível — mesma garantia estrutural de
privacidade do domínio `pii` (a API nunca vê o valor real da coluna, só
contagens agregadas: `COUNTIF` de não-nulo e `COUNTIF` de match por
tipo candidato).

### Critério de sugestão (nunca superestimar)

Uma coluna só vira sugestão se **todas as três** condições baterem:

1. `match_ratio == 1.0` — 100% dos valores não-nulos **amostrados**
   batem no tipo candidato. Não é configurável nesta v1 (diferente do
   `match_threshold_pct` de PII) — aplicar um tipo mais estreito numa
   coluna de produção que não converte 100% quebraria dado real, então
   não faz sentido um limiar "a maioria bate".
2. `sample_non_null_count > 0` — coluna inteiramente nula não sugere
   nada (não há amostra pra basear a sugestão).
3. **Economia de bytes positiva** — `avg_current_bytes >
   suggested_type_bytes` (ver fórmula abaixo). Uma `STRING` curta (ex:
   `"1"`, `"0"`) já ocupa menos espaço que um `INT64` de 8 bytes fixos —
   sugerir a troca nesse caso pioraria o storage, não economizaria.

### Fórmula de bytes (documentada, não é opinião)

Tamanho de armazenamento por tipo, conforme a
[documentação de storage pricing do BigQuery](https://cloud.google.com/bigquery/pricing#storage):

| Tipo | Bytes |
|---|---|
| `STRING` | `2 + BYTE_LENGTH(valor)` (variável) |
| `INT64` / `FLOAT64` / `BOOL`* / `DATE` / `DATETIME` / `TIMESTAMP` | 8 fixos (`BOOL` é 1, os demais 8) |

`avg_current_bytes = 2 + AVG(BYTE_LENGTH(col))` sobre a amostra.
`estimated_storage_savings_usd_month = MAX(0, avg_current_bytes -
suggested_type_bytes) × row_count × settings.bigquery_storage_price_usd_per_gb_month_active
/ 1024³` — usa `row_count` real da tabela (metadado, não a amostra) pra
extrapolar a economia por coluna pro tamanho real da tabela; usa sempre
o preço "active" (não distingue long-term aqui, diferente do scanner de
tabelas sem uso — simplificação aceita pra v1).

*BOOL é 1 byte, mas nunca teria `avg_current_bytes` de STRING menor que
1 byte, então na prática toda sugestão de `BOOL` passa no critério 3.

---

## Endpoints da API

### POST /api/v1/finops/{project_id}/column-type-suggestions/estimate
Dry-run **gratuito** (não executa nenhuma query paga) — soma o
`total_bytes_processed` de todas as queries de scan que seriam
executadas, uma por tabela elegível.

**Body:** `{"sample_percent": 10, "tables": ["RAW.crm_leads", "TRUSTED.orders"]}`
(`sample_percent` default `10`, mínimo `1` — `InvalidSamplePercentError`
se menor; `tables` default `null` — projeto inteiro, ver "Escopo de
execução"; o frontend sempre manda a lista explícita).

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "tables_scanned": 42,
  "tables_skipped_view": 3,
  "columns_scanned": 187,
  "estimated_bytes": 5000000000,
  "estimated_bytes_human": "5.00 GB",
  "estimated_cost_usd": 0.0305,
  "warning": null
}
```

### POST /api/v1/finops/{project_id}/column-type-suggestions/run
Executa de fato — uma query `TABLESAMPLE` por tabela elegível, em
paralelo (`ThreadPoolExecutor`, `max_workers=4` — mais conservador que
os `max_workers=8` de `list_all_table_refs`/`get_date_like_columns`
porque aqui cada query tem custo real, não é `INFORMATION_SCHEMA`
grátis). Orçamento total de `_COLUMN_TYPE_SCAN_TIMEOUT_SECONDS = 120s`
pro lote inteiro — se o tempo acabar no meio, retorna as tabelas já
escaneadas com `warning` avisando que o resultado é parcial (não lança
erro — resultado parcial ainda tem valor, diferente do scan de uma
tabela só em PII/quality, onde parcial não faz sentido).

**Body:** mesmo formato do `/estimate`.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "executed_at": "2026-08-17T10:00:00Z",
  "sample_percent": 10,
  "tables_scanned": 42,
  "tables_skipped_view": 3,
  "candidates": [
    {
      "dataset_id": "RAW",
      "table_id": "crm_leads",
      "size_bytes": 2000000000,
      "row_count": 1000000,
      "suggestions": [
        {
          "column_name": "customer_id",
          "current_type": "STRING",
          "suggested_type": "INT64",
          "sample_non_null_count": 950,
          "avg_current_bytes": 10.2,
          "suggested_type_bytes": 8,
          "estimated_storage_savings_usd_month": 0.0042
        }
      ]
    }
  ],
  "warning": null
}
```
Só tabelas com pelo menos uma sugestão aparecem em `candidates` — mesmo
padrão de "só mostra quem tem achado" do scanner de particionamento
(diferente de PII, que lista toda coluna elegível mesmo sem match, por
ser uma tela de auditoria por tabela; aqui é uma lista de oportunidades
por projeto, então ruído (`0 sugestões`) não ajuda).

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── finops.py               # + POST .../column-type-suggestions/{estimate,run}
├── domains/finops/
│   ├── sql_builder.py           # novo — build_scan_query (mirror de domains/pii/sql_builder.py)
│   ├── repository.py            # + get_string_columns, is_view, dry_run, execute_scan_query
│   ├── service.py               # + estimate_column_type_suggestions, run_column_type_suggestions
│   └── schemas.py               # + ColumnTypeSuggestion, ColumnTypeCandidate, *Response
└── tests/unit/finops/
    ├── test_sql_builder.py       # novo
    ├── test_repository.py        # + testes de get_string_columns/is_view/dry_run/execute
    └── test_service.py           # + testes de estimate/run
```

Frontend:
```
apps/frontend/src/
├── components/ui/checkbox.tsx           # novo, via shadcn CLI
├── features/finops/
│   ├── FinOpsPage.tsx                    # + aba "Tipos de coluna" (ColumnTypesTab)
│   ├── ColumnTypeScopePicker.tsx          # novo — datasets com checkbox, expande em tabelas
│   ├── ColumnTypeSuggestionBadges.tsx     # novo — badges de sugestão, compartilhado entre as duas telas
│   ├── ColumnTypeSuggestionsTab.tsx       # novo — aba do modal de profiling (por tabela)
│   └── hooks.ts                           # + useEstimateColumnTypeSuggestions/useRunColumnTypeSuggestions
├── features/quality/ProfilingDialog.tsx  # + aba "Tipos de coluna" (ColumnTypeSuggestionsTab)
├── lib/api/finops.ts                     # + tables no body de estimate/run
└── types/finops.ts                        # + Column Type*
```

Aba de projeto (`FinOpsPage.tsx`): fluxo em duas etapas
(estimar → escanear) com `ColumnTypeScopePicker` antes dos botões — sem
seleção, botões ficam desabilitados. Tabela de resultado agrupada por
tabela (dataset.tabela → sugestões como badges via
`ColumnTypeSuggestionBadges`), reaproveitando `useTableFilterSort`.

Aba do modal (`ColumnTypeSuggestionsTab.tsx`): mesmo fluxo, mesmo padrão
de `features/pii/PiiTab.tsx`, mas sem seletor — escopo é sempre a tabela
aberta no modal.

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Tabela é VIEW/MATERIALIZED VIEW | Pulada inteiramente (sem `TABLESAMPLE`) — contabilizada em `tables_skipped_view`, não aparece em `candidates` |
| Tabela sem nenhuma coluna `STRING` | Pulada — não gera query nem entra em `tables_scanned` |
| Coluna `STRING` inteiramente nula na amostra | Sem sugestão (`sample_non_null_count == 0`) |
| `match_ratio` amostrado menor que 100% | Sem sugestão — só sugere quando toda a amostra bate, nunca "a maioria" |
| `STRING` curta que já ocupa menos bytes que o tipo sugerido | Sem sugestão — critério 3 do "Critério de sugestão" bloqueia |
| Orçamento de tempo do `/run` esgota no meio do lote | Retorna candidatos das tabelas já escaneadas, `warning` avisa resultado parcial |
| `sample_percent` menor que 1 | HTTP 422 (`InvalidSamplePercentError`) |
| Projeto sem nenhuma tabela | `tables_scanned = 0`, `candidates = []`, sem erro |
| `tables` com entrada mal formada (sem ponto, dataset ou tabela vazios) | Entrada ignorada silenciosamente (`_parse_scoped_tables`) — não derruba o resto do escopo pedido |
| `tables=[]` (usuário não selecionou nada) | `tables_scanned = 0`, `candidates = []` — mesmo resultado de "projeto sem tabela", sem erro; frontend evita chegar aqui desabilitando os botões |

---

## Fora do escopo desta spec

- **Sugestão de clustering** — precisaria de análise de padrão de query
  (quais colunas aparecem em `WHERE`/`GROUP BY`/`JOIN` com mais
  frequência nos audit logs). Sem um parser de SQL de verdade isso vira
  heurística de regex sobre texto livre de query — frágil o bastante
  pra merecer uma spec própria e uma conversa separada sobre nível de
  confiança aceitável, não faz parte desta v1.
- **Aplicar a mudança de tipo de fato** — a ferramenta é somente
  leitura (`docs/prd.md`, "Fora do escopo" do produto); isso aqui é só
  sugestão, a migração de schema é manual, fora do Hub.
- **Validação de dígito verificador ou qualquer regra de negócio
  específica de domínio** — só compatibilidade de tipo bruto
  (`SAFE_CAST`), sem julgar se um `INT64` sugerido faz sentido
  semântico (ex: um CEP que "caberia" em `INT64` mas semanticamente é
  melhor como `STRING` por causa de zeros à esquerda — fora do escopo
  desta v1, decisão fica com quem lê a sugestão).
- **Economia de custo de query** (bytes escaneados) — só storage. Um
  tipo mais estreito também reduziria bytes escaneados em queries
  futuras, mas estimar isso exigiria a mesma especulação sobre padrão
  de query já evitada na decisão de não fazer clustering nesta v1.
- **Colunas não-`STRING`** (ex: `FLOAT64` que só guarda inteiros,
  sugerindo `INT64`) — fora do escopo da v1, mesma lógica poderia se
  estender depois se houver demanda.
