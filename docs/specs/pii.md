# Spec — Domínio: PII (fingerprinting de dados pessoais)

**Versão:** 1.1
**Status:** Aprovada
**Fase:** 3 — Sprint 3.2
**Última atualização:** 2026-08-17

---

## Objetivo

Detectar colunas com dados pessoais (PII) em qualquer tabela BigQuery
acessível, combinando duas camadas: heurística de nome de coluna (grátis,
sem tocar dado real) e amostragem real de valores via `TABLESAMPLE
SYSTEM` com contagem de matches de regex por padrão de PII (custo real de
BQ, com estimativa de custo antes de executar — mesmo padrão do domínio
`quality`). A região é resolvida automaticamente via metadados do
dataset, igual aos demais domínios.

**Garantia de privacidade estrutural**: o matching roda inteiramente
dentro do BigQuery via `REGEXP_CONTAINS` + `COUNTIF` — a API nunca
recebe, processa ou loga um valor de coluna real, só contagens e
proporções agregadas por coluna/tipo. O valor bruto nunca sai do
BigQuery para dentro do processo Python.

---

## Fluxo de uso

```
1. Usuário abre o modal "Analisar" de uma tabela (mesmo modal do
   domínio quality) e clica na aba "PII"
2. Heurística de nome já aparece de cara, sem custo — badge por coluna
   cujo nome bate com algum tipo de PII conhecido (ex: "email_cliente"
   → email)
3. Configura: amostragem %, limiar de sinalização %
   (amostragem desabilitada se a tabela for VIEW/MATERIALIZED VIEW —
   ver "Suporte a views")
4. "Estimar custo" → dry run retorna volume e custo USD + SQL gerado
5. "Escanear" → contagem de matches por coluna/tipo, com flag e nível
   de confiança
```

### Suporte a views

Igual à v1 de profiling: `TABLESAMPLE SYSTEM` não é suportado pelo
BigQuery em `VIEW`/`MATERIALIZED VIEW`. Diferente de profiling — que
ainda roda a query principal sem `TABLESAMPLE` nesse caso — o domínio
PII **pula a query de amostragem inteiramente** quando `is_view=true`:
rodar sem amostragem escanearia a view inteira sem que o usuário tivesse
visto uma estimativa de custo antes (a spec de profiling já aceita esse
custo por ser a funcionalidade central do domínio; PII é uma checagem
complementar, não vale o mesmo risco). Só a heurística de nome é
avaliada nesse caso, com `warning` explicando.

---

## Parâmetros de configuração

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `sample_percent` | float | 10 | % `TABLESAMPLE SYSTEM` (mín: 1) |
| `match_threshold_pct` | float | 5 | % mínimo dos valores não-nulos amostrados que precisa bater no regex pra a coluna ser sinalizada (0–100) |

---

## Endpoints da API

### POST /api/v1/pii/{project_id}/{dataset_id}/{table_id}/estimate
Dry run — bytes e custo estimados sem executar query real.

**Body:**
```json
{ "sample_percent": 10, "match_threshold_pct": 5 }
```

**Response 200:**
```json
{
  "estimated_bytes": 420000,
  "estimated_bytes_human": "420.00 KB",
  "estimated_cost_usd": 0.0000025,
  "sql": "SELECT COUNTIF(`email` IS NOT NULL) AS `email__non_null`, ..."
}
```

`sql: null` e `estimated_bytes: 0` quando não há nenhuma coluna `STRING`
elegível ou quando a tabela é view (ver "Suporte a views") — nada seria
executado.

---

### POST /api/v1/pii/{project_id}/{dataset_id}/{table_id}/run
Executa o scan e retorna a heurística de nome + os resultados da amostra
por coluna.

**Body:** mesmo schema do `/estimate`

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "dataset_id": "RAW",
  "table_id": "crm_leads",
  "executed_at": "2026-08-14T10:00:00Z",
  "is_view": false,
  "parameters": { "sample_percent": 10, "match_threshold_pct": 5 },
  "sql": "...",
  "columns": [
    {
      "column_name": "email_cliente",
      "data_type": "STRING",
      "name_match_types": ["email"],
      "sample_non_null_count": 842,
      "sample_matches": [
        { "pii_type": "email", "match_count": 810, "match_ratio": 0.9620, "flagged": true }
      ],
      "flagged": true,
      "confidence": "high"
    },
    {
      "column_name": "descricao",
      "data_type": "STRING",
      "name_match_types": [],
      "sample_non_null_count": 842,
      "sample_matches": [],
      "flagged": false,
      "confidence": null
    }
  ],
  "excluded_columns": [
    { "column_name": "endereco", "reason": "Tipo STRUCT<rua STRING> não é STRING — sem padrão de PII aplicável nesta versão." }
  ],
  "warning": null
}
```

`columns` traz **todas** as colunas elegíveis (STRING), não só as
sinalizadas — mesmo padrão de `ColumnProfile` em profiling.
`sample_matches` só lista tipos com `match_count > 0` (evita payload
cheio de zeros).

---

## Histórico de scans (v1.1 desta spec, Admin v1.3)

Cada execução real do `/run` (cache miss — ver `_scan_cache` em
`service.py`, TTL de 300s) grava um resumo em
`pii_scan_history/{project}_{dataset}_{table}/scans/{auto-id}`:
`project_id`, `dataset_id`, `table_id`, `executed_by`, `executed_at`,
`flagged_columns_count`, `columns` (resumo mínimo por coluna:
`column_name`, `flagged`, `confidence` — sem valores de amostra, que já
não existem no schema de resposta hoje). Cap de 30 por tabela, mesmo
trim-to-max de `domains/quality/history_repository.py`.

Um **cache hit** não grava histórico de novo — o resultado devolvido é
o mesmo de uma execução anterior, não uma execução nova.

O nome da subcoleção é `scans`, deliberadamente diferente de `runs`
(usado por `profiling_history`) — a agregação administrativa em
`domains/admin/analytics_repository.py` lê ambos via
`collection_group`, que ignora o caminho do documento-pai e enxerga só
o nome da subcoleção; nomes iguais fariam os dois históricos se
misturarem.

Esse histórico alimenta só a visão administrativa agregada
(`GET /api/v1/admin/analytics/pii-scans`, ver `docs/specs/admin.md`) —
não existe endpoint de histórico por tabela nesta versão (diferente de
`quality`, que tem `GET /api/v1/quality/history/...`); adicionar um, se
algum dia for pedido, é extensão pequena sobre o mesmo repository.

---

## Lógica de geração de SQL

### Query de scan (gerada dinamicamente, uma linha só por tabela)
```sql
SELECT
  COUNTIF(`{col}` IS NOT NULL) AS `{col}__non_null`,
  COUNTIF(REGEXP_CONTAINS(`{col}`, r'{pattern_email}'))          AS `{col}__email`,
  COUNTIF(REGEXP_CONTAINS(`{col}`, r'{pattern_cpf}'))            AS `{col}__cpf`,
  COUNTIF(REGEXP_CONTAINS(`{col}`, r'{pattern_cnpj}'))           AS `{col}__cnpj`,
  COUNTIF(REGEXP_CONTAINS(`{col}`, r'{pattern_telefone_br}'))    AS `{col}__telefone_br`,
  COUNTIF(REGEXP_CONTAINS(`{col}`, r'{pattern_cep}'))            AS `{col}__cep`,
  COUNTIF(REGEXP_CONTAINS(`{col}`, r'{pattern_cartao_credito}')) AS `{col}__cartao_credito`
  -- repetido pra cada coluna STRING elegível
FROM `{project}.{dataset}.{table}`
  TABLESAMPLE SYSTEM ({sample_percent} PERCENT)
```

Omite `TABLESAMPLE SYSTEM (...)` (e ignora `sample_percent`) quando a
tabela é `VIEW`/`MATERIALIZED VIEW` — mas nesse caso a query nem chega a
ser montada com colunas (`run_pii_scan` força `string_columns=[]` pra
view, ver "Suporte a views"), então na prática `sql=null` sempre que
`is_view=true`.

### Padrões regex (RE2 — `REGEXP_CONTAINS` do BigQuery não suporta
lookahead/backreference; formato apenas, sem validação de dígito
verificador)

| Tipo | Padrão |
|---|---|
| `email` | `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` |
| `cpf` | `\d{3}\.\d{3}\.\d{3}-\d{2}` |
| `cnpj` | `\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}` |
| `telefone_br` | `(\(\d{2}\)\s?)?9?\d{4}-\d{4}` |
| `cep` | `\d{5}-\d{3}` |
| `cartao_credito` | `\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}` |

### Heurística de nome de coluna (grátis, `INFORMATION_SCHEMA.COLUMNS`
apenas)

Substring case-insensitive do nome da coluna contra keywords por tipo
(`domains/pii/sql_builder.py::NAME_HEURISTIC_KEYWORDS`) — ex: coluna
`num_cartao_cliente` bate `cartao_credito` por conter `"cartao"`.

---

## Regras de flagging e confidence

### `flagged` por tipo (`PiiTypeMatch`)
`match_ratio = match_count / sample_non_null_count` (0 se
`sample_non_null_count == 0`). `flagged = match_ratio * 100 >=
match_threshold_pct` (limiar inclusivo — exatamente no limiar já
sinaliza).

### `flagged` por coluna (`PiiColumnResult`)
`name_match_types` não-vazio **OU** algum `sample_matches[].flagged`.

### `confidence`
| Confidence | Critério |
|---|---|
| `high` | Nome bate **e** amostra sinaliza algum tipo |
| `medium` | Só nome bate, ou só amostra sinaliza (não os dois) |
| `null` | Nenhum dos dois |

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── pii.py
├── domains/pii/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py
│   ├── history_repository.py  # novo (v1.1) — pii_scan_history/{doc}/scans
│   ├── sql_builder.py      # Padrões regex, heurística de nome, geração de SQL
│   └── schemas.py
└── tests/unit/pii/
    ├── test_service.py
    ├── test_history_repository.py  # novo (v1.1)
    └── test_sql_builder.py  # Testa geração de SQL sem tocar BQ
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Tabela sem nenhuma coluna `STRING` | `sql=null`, só heurística de nome, `warning` explica |
| View/Materialized View | Query de amostragem pulada inteiramente (não só `TABLESAMPLE` omitido), `warning` explica |
| Coluna `STRUCT`/`ARRAY`/`BYTES`/numérica/data | `excluded_columns`, razão por tipo |
| `match_ratio` exatamente no limiar | `flagged=true` (`>=`, não `>`) |
| Nenhuma coluna bate em nenhum padrão | `columns` retorna todas com `flagged=false`, sem erro |
| CPF/CNPJ/telefone/cartão sem formatação (dígitos crus) | Não detectado nesta v1 — só padrão formatado |
| Mesmo `/run` dentro de 5min (mesmos parâmetros) | Cache em memória (`_scan_cache`, TTL 300s), não reexecuta a query paga |
| Timeout > 60s | HTTP 504 com sugestão de reduzir amostragem |
| `sample_percent < 1` | HTTP 400 |
| `match_threshold_pct` fora de 0–100 | HTTP 422 (validação Pydantic) |
| Cache hit dentro dos 5min | Não grava novo doc em `pii_scan_history` — não é uma execução real |
| Tabela escaneada mais de 30 vezes | Trim automático mantém só os 30 scans mais recentes |

---

## Fora do escopo desta spec

- Validação de dígito verificador (CPF/CNPJ) e algoritmo de Luhn
  (cartão de crédito) — regex de formato apenas; falso positivo (ex:
  CPF com dígitos verificadores inválidos mas formato correto) e falso
  negativo (CPF válido sem formatação) são limitações conhecidas.
- Detecção de CPF/CNPJ/telefone/cartão sem formatação (dígitos crus,
  sem pontuação) — alto risco de falso positivo contra qualquer
  sequência numérica do tamanho certo.
- Detecção de nome de pessoa — sem padrão regex confiável.
- Tipo `BYTES` — fora do escopo desta versão.
- Persistência/histórico de scans (diferente de profiling, que salva no
  Firestore) — cada scan é on-demand, sem aba "Histórico" nesta v1.
- Mascaramento/redação de valores reais — a API nunca retorna nem loga
  o valor encontrado, só contagens agregadas (ver "Garantia de
  privacidade estrutural").
- Mapa de acesso / quem consultou quais colunas de PII (domínio
  separado, `domains/access`, Fase 3).
