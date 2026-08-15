# Spec — Domínio: Mapa de acesso

**Versão:** 1.0
**Status:** Aprovada
**Fase:** 3 — Sprint 3.2
**Última atualização:** 2026-08-14

---

## Objetivo

Mostrar quem acessou uma tabela e quando, distinguindo usuários humanos
de service accounts. Reaproveita a mesma fonte de dados do lineage
(audit logs de jobs BigQuery via Cloud Logging) sob um ângulo diferente:
lineage pergunta "de onde vem/pra onde vai esse dado", mapa de acesso
pergunta "quem tocou nessa tabela".

---

## Fonte de dados

Cloud Logging — audit logs de jobs do BigQuery (`jobservice.jobcompleted`),
**custo $0**, mesma janela e mesmo formato de payload que `domains/lineage`
(`LOOKBACK_DAYS = 30`, formato legado `AuditData`/`jobCompletedEvent` —
ver `docs/specs/lineage.md`, "Fonte de dados"). `domains/access/repository.py`
duplica o parsing em vez de importar de `domains/lineage` (domínios não
importam um do outro), com uma diferença: também extrai
`jobStatistics.endTime` como timestamp do acesso — campo que lineage não
precisa e por isso não lê.

**Limitação de visibilidade (mesma classe da já documentada em lineage/
órfãs)**: só aparecem acessos originados por jobs que **rodaram no
projeto da tabela consultada**. Um job rodando em outro projeto que lê
essa tabela via referência cross-project não aparece — o audit log desse
job vive no projeto onde ele rodou, não no projeto da tabela lida. Não
há hoje um jeito de descobrir "quais outros projetos podem ter acessado
essa tabela" sem já saber quais projetos verificar.

---

## Endpoints da API

### GET /api/v1/access/{project_id}/{dataset_id}/{table_id}
Últimos usuários que acessaram a tabela (leitura ou escrita), mais
recente primeiro.

**Parâmetros opcionais:**
- `limit` (query, default `20`, mínimo `1`, máximo `100`) — quantos
  usuários distintos retornar.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "dataset_id": "RAW",
  "table_id": "crm_leads",
  "lookback_days": 30,
  "users": [
    {
      "principal_email": "ana@dp6.com.br",
      "is_service_account": false,
      "last_accessed_at": "2026-08-14T10:00:00Z",
      "access_count": 5,
      "access_types": ["read"]
    },
    {
      "principal_email": "backend-run@observability-hub-dev.iam.gserviceaccount.com",
      "is_service_account": true,
      "last_accessed_at": "2026-08-13T22:00:00Z",
      "access_count": 12,
      "access_types": ["read", "write"]
    }
  ],
  "warning": null
}
```

---

## Lógica de agregação

```python
# domains/access/service.py
def get_table_access(
    logging_client: cloud_logging.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    limit: int = 20,
) -> TableAccessResponse:
    """
    1. Busca todos os eventos de job do projeto na janela de 30 dias
       (repository.list_access_events — mesma chamada de lineage).
    2. Por evento, compara a tripla completa (project_id, dataset_id,
       table_id) — nunca só (dataset_id, table_id), mesmo motivo do bug
       corrigido na v2 do lineage (colisão entre projetos com dataset/
       tabela de mesmo nome):
       - tabela alvo em referenced_tables -> tipo "read"
       - tabela alvo == destination_table -> tipo "write"
       Um job pode contribuir os dois tipos ao mesmo tempo (ex: MERGE
       lendo e escrevendo a própria tabela) — diferente do lineage, essa
       auto-referência NÃO é excluída aqui: pra mapa de acesso, é um
       acesso real, não uma relação de dependência entre tabelas
       (lineage exclui porque ali representaria um ciclo sem sentido).
    3. Evento sem timestamp (jobStatistics.endTime ausente/malformado)
       é ignorado — sem "quando" não é útil pro mapa de acesso.
    4. Agrega por principal_email: access_count (nº de jobs distintos
       que tocaram a tabela), last_accessed_at (timestamp mais recente),
       access_types (união dos tipos vistos).
    5. is_service_account = principal_email termina em
       "gserviceaccount.com".
    6. Ordena por last_accessed_at desc, corta em `limit`.
    """
```

`get_table_lineage`/`get_orphans` (domínio `lineage`) não mudam — este é
um domínio novo e independente, só compartilhando a fonte de dados.

### Exclusão da SA do próprio Hub

Antes de agregar, todo evento cujo `principal_email` seja
`backend-run@<projeto-do-hub>.iam.gserviceaccount.com` (`<projeto-do-hub>`
= `core/bigquery.py::get_client().project`, o projeto onde a instância
do Hub está rodando — dev ou prod, não o projeto da tabela consultada)
é descartado antes de entrar em `by_principal`.

Motivo: toda vez que o usuário roda profiling ou scan de PII numa
tabela pela própria UI do Hub, quem executa a query real no BigQuery é
essa SA de runtime (`core/bigquery.py::get_client()`), não o usuário.
Sem esse filtro, o simples ato de inspecionar uma tabela pelo Hub faria
ela aparecer como "acesso recente" no próprio mapa de acesso — ruído
que mascararia os consumidores externos reais, o oposto do que a
funcionalidade existe pra mostrar. Outras service accounts (pipelines
externos, Glue, etc.) continuam contando normalmente — só a SA do
próprio Hub é excluída.

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── access.py          # GET /access/{project_id}/{dataset_id}/{table_id}
├── domains/access/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py      # list_access_events() — duplica parsing de lineage + timestamp
│   └── schemas.py
└── tests/unit/access/
    ├── test_service.py
    └── test_repository.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Job lê e escreve a própria tabela (MERGE) | Conta como acesso com `access_types: ["read", "write"]` — diferente do lineage, não é excluído |
| Job sem `jobStatistics.endTime` válido | Ignorado (sem timestamp, não entra na agregação) |
| Mesmo usuário com múltiplos jobs na janela | Um único registro, `access_count` somado, `last_accessed_at` = mais recente |
| Tabela referenciada por job de **outro** projeto | Ignorada — comparação é pela tripla completa `(project_id, dataset_id, table_id)` |
| Job rodando em outro projeto, lendo esta tabela via cross-project | Não aparece — audit log vive no projeto onde o job rodou, não no da tabela (ver "Fonte de dados") |
| Nenhum evento de job no projeto | `warning` populado (mesmo texto/causas de lineage), `users: []` |
| `limit` fora do intervalo 1–100 | HTTP 422 (validação do `Query(ge=1, le=100)`) |
| Job executado pela própria SA de runtime do Hub (`backend-run@<projeto-do-hub>.iam.gserviceaccount.com`) | Excluído da agregação — profiling/PII rodado pela UI usa essa SA pra consultar o BigQuery, não é um consumidor externo real (ver "Exclusão da SA do próprio Hub") |
| Job de outra service account (ex: pipeline externo) | Conta normalmente, `is_service_account: true` |

---

## Fora do escopo desta spec

- Visão por usuário ("quais tabelas o usuário X acessou") — esta versão
  é só por tabela; a pergunta inversa fica pra uma versão futura se
  houver demanda.
- Acessos via BigQuery Storage Read API direto (conectores tipo Spark/
  Glue que pulam o motor de query) — não aparecem em
  `jobservice.jobcompleted`, mesma lacuna já discutida informalmente
  pro caso de um job Glue extraindo dados do BQ pra S3.
- Persistência histórica além da janela de 30 dias (sem Firestore aqui,
  diferente de quality) — cada consulta reflete só a janela corrente dos
  audit logs.
- Alertas de acesso anômalo/fora do padrão (fase futura, FinOps/
  governança).
