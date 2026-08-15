# Onboarding de projeto GCP — acesso do Observability Hub

**Objetivo:** checklist completo de tudo que precisa ser configurado em um
projeto GCP "alvo" (projeto de cliente, ou qualquer projeto que não seja
`observability-hub-dev`/`observability-hub-prod`) para que o Hub consiga
observá-lo — catálogo, freshness, profiling e lineage/tabelas órfãs.

Modelo de acesso: **Modelo A — service account com acesso cross-project**
(ver [ADR-006](adr/ADR-006-cross-project.md)). O Hub nunca instala nada no
projeto alvo — o administrador do lado do cliente concede acesso de leitura
à service account de runtime do Hub, uma vez, e o `project_id` é digitado
pelo usuário no frontend a cada sessão.

**Quem executa:** o administrador do projeto alvo (cliente). O time do Hub
só fornece os comandos prontos — nunca tem credenciais próprias do lado do
cliente.

---

## 1. Habilitar APIs no projeto alvo

```bash
gcloud services enable bigquery.googleapis.com logging.googleapis.com \
  --project={PROJECT_ID}
```

`logging.googleapis.com` é necessário mesmo que o projeto não gere logs
propositalmente — é o transporte usado por lineage e (futuramente) mapa de
acesso.

---

## 2. IAM — conceder acesso à service account de runtime do Hub

Qual service account usar depende de qual ambiente do Hub vai consultar o
projeto:

| Ambiente do Hub | Service account |
|---|---|
| Produção (uso real com cliente) | `backend-run@observability-hub-prod.iam.gserviceaccount.com` |
| Dev (teste interno) | `backend-run@observability-hub-dev.iam.gserviceaccount.com` |

Roles necessárias — granularidade sempre a nível de **projeto** (nenhum
domínio hoje opera com IAM a nível de dataset ou tabela):

| Role | Por quê | Domínio(s) que usa |
|---|---|---|
| `roles/bigquery.metadataViewer` | Ler `INFORMATION_SCHEMA` (schemas, tabelas, colunas, particionamento) | catalog, freshness, lineage (`discover_regions`) |
| `roles/bigquery.jobUser` | Executar queries — inclusive as de `INFORMATION_SCHEMA`, que rodam como job no BigQuery | catalog, freshness, quality, lineage |
| `roles/bigquery.dataViewer` | Ler dados reais de tabela (amostragem, contagem de nulos/duplicatas, valores distintos) | quality (profiling e histórico) |
| `roles/logging.viewer` | Chamar a API de Cloud Logging sem 403 — sozinha **não é suficiente** pra ver Data Access audit logs, ver nota abaixo | lineage (tabelas órfãs, upstream/downstream); mapa de acesso quando implementado |
| `roles/logging.privateLogViewer` | Ver especificamente os **Data Access audit logs** — é onde vive o `jobCompletedEvent` que lineage lê; sem essa role a chamada não falha, só retorna sempre vazio | idem |

> **Pegadinha confirmada em produção (2026-08-14):** `roles/logging.viewer`
> sozinha deixa a API responder 200 normalmente, mas Data Access audit logs
> (categoria diferente de Admin Activity, que fica sempre visível) só ficam
> visíveis pra quem também tem `roles/logging.privateLogViewer` — sem ela,
> `entries.list` não erra, só nunca retorna nenhuma entrada da categoria
> Data Access. As duas roles são necessárias juntas, não uma ou outra.
> ([doc oficial](https://docs.cloud.google.com/logging/docs/access-control))

```bash
SA_EMAIL="backend-run@observability-hub-prod.iam.gserviceaccount.com"  # ou -dev

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.metadataViewer"

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/logging.viewer"

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/logging.privateLogViewer"
```

Todos os cinco comandos são idempotentes — seguro rodar de novo mesmo que
algum já tenha sido aplicado. Se faltar qualquer uma das três primeiras, a
API responde 403 com esses mesmos comandos prontos no corpo do erro
(`ProjectAccessDeniedError`); se faltar `logging.viewer`, o mesmo acontece
só pros endpoints de lineage (`LoggingAccessDeniedError`, que já sugere as
duas roles de logging juntas); se faltar só `logging.privateLogViewer`
(com `logging.viewer` presente), não há erro nenhum — só o aviso de
"nenhum evento encontrado", indistinguível à primeira vista de "sem
atividade real" ou "audit logs desabilitados". Checar as três
possibilidades nessa ordem quando o aviso aparecer sem explicação óbvia.

---

## 3. Data Access audit logs do BigQuery — habilitar

`roles/logging.viewer` sozinho não é suficiente. Lineage e tabelas órfãs
dependem de o evento `jobCompletedEvent` estar sendo escrito nos logs, e
isso só acontece se **Data Access audit logs** do BigQuery estiverem
habilitados no projeto — Admin Activity logs (sempre ativos, não precisam
de configuração) não incluem esse evento.

Sem isso, os endpoints de lineage respondem `200 OK` com uma lista vazia e
um aviso — não é um erro, mas o dado fica sempre vazio até habilitar.

**Via console:** IAM & Admin → Audit Logs → localizar "BigQuery API" →
marcar "Data Read" e "Data Write" → Save.

**Via gcloud** (getIamPolicy/setIamPolicy — cuidado para não sobrescrever
outras configurações de audit já existentes no projeto; sempre ler a
política atual primeiro):

```bash
gcloud projects get-iam-policy {PROJECT_ID} --format=json > policy.json
# editar policy.json, adicionar/mesclar o bloco abaixo em "auditConfigs"
```

```json
{
  "auditConfigs": [
    {
      "service": "bigquery.googleapis.com",
      "auditLogConfigs": [
        { "logType": "DATA_READ" },
        { "logType": "DATA_WRITE" }
      ]
    }
  ]
}
```

```bash
gcloud projects set-iam-policy {PROJECT_ID} policy.json
```

`ADMIN_READ` não é necessário para lineage (não captura `jobCompletedEvent`
de query/load), mas não atrapalha se já estiver habilitado por outro
motivo.

---

## 4. O que NÃO é necessário

- Nenhum agente, VM ou service account do lado do cliente rodando código —
  o Hub só lê, via API, a partir de fora do projeto.
- `roles/billing.viewer` / Cloud Billing — não é necessário ainda; domínio
  FinOps não implementado (ver CLAUDE.md, tabela de domínios).
- Secret Manager, Artifact Registry, Cloud Run, Firestore — recursos
  internos do Hub, vivem só em `observability-hub-{dev,prod}`, nunca no
  projeto alvo.

---

## Checklist resumido

```
[ ] bigquery.googleapis.com habilitada no projeto alvo
[ ] logging.googleapis.com habilitada no projeto alvo
[ ] roles/bigquery.metadataViewer concedida à SA do Hub
[ ] roles/bigquery.jobUser concedida à SA do Hub
[ ] roles/bigquery.dataViewer concedida à SA do Hub
[ ] roles/logging.viewer concedida à SA do Hub
[ ] roles/logging.privateLogViewer concedida à SA do Hub — sem ela,
    logging.viewer sozinha NÃO mostra Data Access audit logs (falha
    silenciosa, sem erro, só resultado sempre vazio)
[ ] Data Access audit logs (DATA_READ + DATA_WRITE) do BigQuery habilitados
    — só necessário se o cliente for usar lineage/tabelas órfãs/mapa de acesso
```

---

## Registro de acessos concedidos (log vivo)

Nenhum projeto de cliente real foi onboardado ainda. As únicas concessões
cross-project existentes até agora são entre os dois ambientes do próprio
Hub (`observability-hub-dev` ↔ `observability-hub-prod`), usadas como
projeto "alvo" de teste um do outro — seguem exatamente este mesmo
checklist, e servem de precedente real de que o processo funciona.

| Data | Projeto alvo | SA concedida | O que foi feito | Confirmado via |
|---|---|---|---|---|
| Sprint 2 (antes de 2026-08-13) | `observability-hub-dev` | `backend-run@...-prod` | `bigquery.metadataViewer` + `jobUser` + `dataViewer` | `gcloud projects get-iam-policy` |
| Sprint 2 (antes de 2026-08-13) | `observability-hub-prod` | `backend-run@...-dev` | `bigquery.metadataViewer` + `jobUser` + `dataViewer` | `gcloud projects get-iam-policy` |
| Antes de 2026-08-14 (sessão não documentada no SESSIONLOG) | `observability-hub-dev` e `observability-hub-prod` | SA própria de cada projeto (self, não cross) | `roles/logging.viewer` concedida | `gcloud projects get-iam-policy` |
| Antes de 2026-08-14 (sessão não documentada no SESSIONLOG) | `observability-hub-dev` e `observability-hub-prod` | — | Data Access audit logs do BigQuery (`DATA_READ`, `DATA_WRITE`, `ADMIN_READ`) habilitados | `gcloud projects get-iam-policy` (campo `auditConfigs`) |
| 2026-08-14 | `observability-hub-prod` | `backend-run@...-dev` | `roles/logging.viewer` (cross) | `gcloud projects get-iam-policy` |
| 2026-08-14 | `observability-hub-dev` | `backend-run@...-prod` | `roles/logging.viewer` (cross) | `gcloud projects get-iam-policy` |
| 2026-08-14 | `observability-hub-prod` | `backend-run@...-dev` | `roles/logging.privateLogViewer` (cross) — **pendente**, comando fornecido nesta sessão | aguardando confirmação |
| 2026-08-14 | `observability-hub-dev` | `backend-run@...-prod` | `roles/logging.privateLogViewer` (cross) — **pendente**, comando fornecido nesta sessão | aguardando confirmação |

**Nota:** os dois itens "antes de 2026-08-14" foram descobertos ao vivo
nesta sessão via `gcloud projects get-iam-policy` — o SESSIONLOG.md
registrava esse estado como pendente (backlog itens 8 e 9), mas já tinha
sido resolvido manualmente pelo usuário em algum momento entre sessões sem
atualizar a documentação. Ver SESSIONLOG.md para a correção desses itens.

**Nota 2 (correção):** a primeira versão deste documento, escrita mais
cedo nesta mesma sessão, listava `roles/logging.privateLogViewer` como
"não lida por nenhum código atual, não replicar em onboarding de
cliente" — **isso estava errado**. Só ficou claro depois que o usuário
testou lineage cross-project em produção e recebeu "nenhum evento
encontrado" mesmo com dados reais existindo (confirmado via
`gcloud logging read` direto): `roles/logging.viewer` deixa a API
responder sem erro, mas **não é suficiente** pra ver Data Access audit
logs — só `roles/logging.privateLogViewer` mostra essa categoria
especificamente. As duas roles voltaram a fazer parte do checklist
oficial (seção 2 acima). Erro registrado aqui de propósito, como exemplo
do próprio processo que este documento existe pra evitar.

Roles concedidas às SAs do Hub que **não fazem parte deste checklist**
(específicas da infraestrutura própria do Hub, nunca pedidas a um projeto
cliente): `roles/datastore.user`, `roles/secretmanager.secretAccessor`
(cada uma só no próprio projeto, `dev` na SA de dev e `prod` na SA de
prod).

---

## Como manter este documento atualizado

Ver CLAUDE.md, seção "Registro de acessos e configurações" — toda vez que
um acesso, role, API ou audit config for concedido/alterado em qualquer
projeto (cliente real ou os próprios `dev`/`prod` do Hub servindo de
projeto-alvo um do outro), a linha correspondente entra na tabela acima
antes de considerar a tarefa concluída.
