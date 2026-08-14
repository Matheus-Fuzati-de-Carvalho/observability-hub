# Spec — Domínio: Lineage e tabelas órfãs

**Versão:** 2.0 (cadeia transitiva multi-hop, cross-project, diagrama)
**Status:** Aprovada
**Fase:** 3 — Sprint 3.2 (lineage e órfãos)
**Última atualização:** 2026-08-14

---

## Histórico

A v1 (upstream/downstream restrito a 1 hop direto) foi implementada nos
commits `f18dfab`/`c33f950`/`0d28700`/`778e3fa` sem uma spec formal — este
documento nasce já como v2, cobrindo a extensão para cadeia transitiva
completa, e formaliza retroativamente o que já valia para a v1 (fonte de
dados, formato de audit log, aviso de resultado vazio).

---

## Objetivo

Reconstruir a cadeia completa de dependências de uma tabela BigQuery —
não só quem lê/escreve diretamente nela, mas toda a sequência de tabelas
intermediárias até onde a trilha de audit logs permitir (ex:
`GOLD.daily_summary` ← `TRUSTED.ga4_sessions` ← `RAW.ga4_events`),
representada como um grafo dirigido (nós = tabelas, arestas = jobs que
leram uma tabela e escreveram outra). Toda tabela é sempre identificada
com o prefixo do projeto (`project.dataset.table`), inclusive quando a
cadeia atravessa mais de um projeto GCP. Uma tabela gerada por `JOIN` de
duas fontes aparece no grafo com duas arestas de entrada (fan-in) — é a
forma natural de um grafo dirigido, não um caso especial.

Também mantém a detecção de tabelas órfãs (sem consumidor conhecido) do
projeto — esse endpoint continua 1-nível, não muda nesta versão (ver
"Fora do escopo").

---

## Fonte de dados

Cloud Logging — audit logs de jobs do BigQuery (`jobservice.jobcompleted`),
**custo $0** (é uma API de logs, não uma query BigQuery faturável):

- Formato legado `AuditData`/`jobCompletedEvent`
  (`google.cloud.bigquery.logging.v1.AuditData`), confirmado contra logs
  reais de `observability-hub-dev` — não o formato novo
  `BigQueryAuditMetadata`/`jobChange`. `referencedTables`/
  `destinationTable` vêm como dicts `{projectId, datasetId, tableId}`.
- Janela fixa: `LOOKBACK_DAYS = 30` (`domains/lineage/repository.py`), não
  configurável via parâmetro de API.
- Depende de **Data Access audit logs** habilitados no projeto (categoria
  opcional, diferente de Admin Activity logs, sempre ativos) e da SA de
  runtime ter `roles/logging.privateLogViewer` (não basta
  `roles/logging.viewer` — a chamada não falha, só retorna vazio). Quando
  o resultado vem vazio, a API devolve um aviso estático
  (`service._EMPTY_RESULT_WARNING`) explicando as três causas possíveis.

**Diferença da v1**: a travessia agora pode precisar consultar o Cloud
Logging de **mais de um projeto** — um por projeto distinto encontrado
durante a expansão do grafo, não só o projeto da tabela raiz. Isso não é
uma mudança de modelo de acesso: o ADR-006 já prevê a SA do Hub com
acesso simultâneo a múltiplos projetos-alvo (é só rodar o comando de
concessão uma vez por projeto, ver `docs/onboarding-cliente.md`) — é um
novo *padrão de uso* de um acesso que já podia existir. Cada projeto
distinto tocado pela travessia é consultado **no máximo uma vez por
requisição** (cache em memória por request, ver "Algoritmo de
travessia").

`GET /api/v1/lineage/{project_id}/orphans` continua também usando
`INFORMATION_SCHEMA.TABLES` (metadado gratuito, via
`domains/catalog`-style `discover_regions` + `list_all_table_refs`) para
levantar o universo de tabelas do projeto, comparado contra o conjunto de
tabelas referenciadas por algum job — inalterado da v1.

---

## Endpoints da API

### GET /api/v1/lineage/{project_id}/{dataset_id}/{table_id}
Retorna o grafo de lineage transitivo em torno da tabela informada.

**Parâmetros opcionais:**
- `max_hops` (query, default `8`, mínimo `1`, máximo `15`) — limite de
  saltos por direção (upstream e downstream são limitados
  independentemente; o alcance total da cadeia pode ser até
  `2 × max_hops`).

**Response 200:**
```json
{
  "root": { "project_id": "observability-hub-dev", "dataset_id": "GOLD", "table_id": "daily_summary" },
  "nodes": [
    {
      "id": "observability-hub-dev:TRUSTED:ga4_sessions",
      "project_id": "observability-hub-dev",
      "dataset_id": "TRUSTED",
      "table_id": "ga4_sessions",
      "hop_distance": -1,
      "is_root": false,
      "access_denied": false
    },
    {
      "id": "observability-hub-dev:RAW:ga4_events",
      "project_id": "observability-hub-dev",
      "dataset_id": "RAW",
      "table_id": "ga4_events",
      "hop_distance": -2,
      "is_root": false,
      "access_denied": false
    }
  ],
  "edges": [
    { "source": "observability-hub-dev:RAW:ga4_events", "target": "observability-hub-dev:TRUSTED:ga4_sessions", "job_id": "job-abc" },
    { "source": "observability-hub-dev:TRUSTED:ga4_sessions", "target": "observability-hub-dev:GOLD:daily_summary", "job_id": "job-def" }
  ],
  "lookback_days": 30,
  "max_hops": 8,
  "truncated": false,
  "warning": null
}
```

A tabela raiz **não** entra em `nodes` (só em `root`) — o frontend
sintetiza o nó raiz a partir desse campo. `hop_distance` é negativo para
upstream, positivo para downstream, sempre relativo à raiz (distância
mais curta encontrada, já que a travessia é BFS). `truncated=true`
quando `max_hops` foi atingido em alguma direção com fronteira ainda não
expandida — há possivelmente mais tabelas além do que foi retornado.

**Response 403** (sem acesso de Logging no projeto **raiz**): mesmo
comportamento da v1 — `LoggingAccessDeniedError` propaga, HTTP 403 com
comando de correção (`handle_logging_access_denied` em `main.py`). Sem
dados do projeto raiz não há nada pra montar. Projetos **não-raiz**
atingidos durante a expansão que não tenham acesso concedido **não**
derrubam a requisição — ver "Casos de borda".

---

### GET /api/v1/lineage/{project_id}/orphans
Inalterado da v1 — ver `OrphansResponse`/`OrphanTable` em
`domains/lineage/schemas.py`. Continua 1-nível: uma tabela é órfã se
nenhum job no projeto a referenciou como fonte na janela de 30 dias,
independente de cadeias transitivas.

---

## Algoritmo de travessia

```python
# domains/lineage/service.py
def get_table_lineage(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    max_hops: int = 8,
) -> LineageGraphResponse:
    """
    BFS a partir da tabela raiz, independente em cada direção
    (upstream/downstream):

    1. Busca os eventos do projeto raiz (sem guarda — falha 403 propaga,
       igual v1). Semeia um cache de eventos por projeto
       (`events_cache: dict[project_id, list[JobEvent]]`) e um conjunto
       de projetos negados (`denied_projects: set[str]`), compartilhados
       pelas duas direções.
    2. Cada direção mantém seu próprio conjunto de nós visitados
       (`(project_id, dataset_id, table_id)`), semeado com a raiz —
       cycle-safe: revisitar um nó já visitado ainda registra a aresta
       de conexão, mas não expande o nó de novo.
    3. Por nível de BFS: para cada job do nó atual, upstream olha
       `referenced_tables` de jobs cujo `destination_table` é o nó atual;
       downstream olha o `destination_table` de jobs que referenciam o nó
       atual. Comparação sempre pela 3-tupla completa
       (project_id, dataset_id, table_id) — nunca só (dataset_id,
       table_id), que era o bug da v1 (colisão possível entre projetos
       diferentes com dataset/tabela de mesmo nome).
    4. Auto-referência (job cujo destino é a própria fonte, ex: MERGE)
       nunca vira aresta, em nenhum hop — mesma exclusão da v1, aplicada
       uniformemente em toda a travessia.
    5. Vizinho novo, dentro do limite de max_hops: busca eventos do
       projeto dele (cache por request — no máximo uma chamada de
       list_job_events por projeto por requisição, mesmo que a travessia
       toque esse projeto por caminhos diferentes ou pelas duas
       direções). Falha de acesso (LoggingAccessDeniedError) nesse
       projeto marca o nó como access_denied=True e não expande esse
       ramo — resto do grafo segue intacto.
    6. Vizinho novo, no limite de max_hops: nó é registrado mas não
       expandido; marca truncated=True.
    7. Fusão final: une nós/arestas das duas direções, dedup por id
       (nó) e por (source, target) (aresta) — necessário porque um ciclo
       que passa pela raiz (ex: A→B→A) pode ser descoberto
       independentemente pelas duas travessias direcionais.
    """
```

JOIN com múltiplas fontes não precisa de tratamento especial: um job com
`referenced_tables=[A, B]` e `destination_table=C` gera as arestas `A→C`
e `B→C` no mesmo passo de expansão — é exatamente o fan-in que o pedido
original descreve.

Deduplicação de aresta é por par `(source, target)`, não por job: como
`list_job_events` não garante ordenação e um job agendado diariamente
gera até 30 eventos repetidos na janela de 30 dias, cada par de tabelas
vira **uma** aresta (mesmo comportamento de dedup por `set()` que a v1 já
tinha para upstream/downstream). `job_id` na aresta é informativo — um
job observado para aquele par, não necessariamente o mais recente (não
há timestamp plumbado em `JobEvent` hoje).

`get_orphans` não muda — continua a lógica 1-nível já existente,
filtrando `ref[0] == project_id`.

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── lineage.py         # GET /lineage/{project_id}/{dataset_id}/{table_id}, /orphans
├── core/
│   ├── exceptions.py      # LoggingAccessDeniedError
│   └── logging_client.py  # get_logging_client()
├── domains/lineage/
│   ├── __init__.py
│   ├── service.py         # BFS bidirecional, cache por projeto, merge
│   ├── repository.py      # list_job_events(), list_all_table_refs() — inalterado
│   └── schemas.py         # LineageNode, LineageEdge, LineageGraphResponse, TableRef, OrphanTable, OrphansResponse
└── tests/unit/lineage/
    ├── test_service.py
    └── test_repository.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Auto-referência (MERGE escreve na própria fonte) | Nunca vira aresta, em nenhum hop |
| Dataset destino anônimo (`_...`, cache de query interativa) | Tratado como sem destino na origem (`repository._parse_entry`), não gera aresta |
| `JOIN` com múltiplas fontes | Fan-in: duas (ou mais) arestas independentes convergindo no mesmo nó |
| Tabela em projeto sem acesso de Logging, **não-raiz** | Nó marcado `access_denied=true`, ramo não expandido, resto do grafo intacto |
| Tabela raiz em projeto sem acesso de Logging | HTTP 403 (hard-fail, igual v1 — sem dado nenhum pra montar) |
| Ciclo (`A→B→A`, jobs diferentes) | Nós/arestas aparecem uma vez cada após a fusão; travessia não reprocessa nó já visitado |
| `max_hops` atingido com fronteira não vazia | `truncated: true` na resposta |
| Job repetido diariamente na janela (mesma aresta) | Deduplicada — uma aresta por par `(source, target)`, não uma por job |
| Nenhum evento de job no projeto raiz | `warning` populado (mesmo texto/causas da v1), `nodes`/`edges` vazios |
| `max_hops` fora do intervalo 1–15 | HTTP 422 (validação do `Query(ge=1, le=15)`) |

---

## Fora do escopo desta spec

- Página de tabelas órfãs (`GET /orphans`) — continua 1-nível, lista
  plana, não vira grafo.
- Histórico/time-travel de schema ao longo da cadeia (lineage reflete o
  estado atual dos nomes de tabela, não versões anteriores).
- Drill-down por job individual na aresta — cada aresta carrega só um
  `job_id` informativo, não a lista completa de jobs que geraram aquela
  relação na janela.
- Detecção de PII ao longo da cadeia (domínio separado, `domains/pii`).
- Configuração de `LOOKBACK_DAYS` via parâmetro de API (continua fixo em
  30 dias, só `max_hops` é parametrizável nesta versão).
