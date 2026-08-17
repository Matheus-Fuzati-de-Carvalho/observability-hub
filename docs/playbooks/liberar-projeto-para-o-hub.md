# Playbook — Liberar um projeto GCP existente para o Hub consumir

**Pergunta que este playbook responde:** "eu já tenho um projeto GCP com
dados no BigQuery — o que eu preciso fazer pra deixar as contas
`observability-hub-dev`/`observability-hub-prod` lerem esse projeto?"

**Não é a fonte de verdade** — é o roteiro de execução rápida. A
referência técnica completa (por quê de cada role, casos de borda,
pegadinhas já vividas em produção) e o **registro vivo de tudo que já foi
concedido** vivem em [`docs/onboarding-cliente.md`](../onboarding-cliente.md).
Depois de executar este playbook, volte lá e registre a linha — ver passo
6 abaixo.

---

## 1. Contexto em 30 segundos

- Modelo de acesso: **cross-project** ([ADR-006](../adr/ADR-006-cross-project.md)).
  O Hub nunca instala nada no projeto alvo. A service account de runtime
  do Hub recebe roles de **leitura** nesse projeto, uma vez; a partir daí
  qualquer usuário do Hub pode digitar esse `project_id` no seletor.
- **Quem executa:** o administrador do projeto alvo (o "cliente"). O time
  do Hub só fornece os comandos prontos abaixo — nunca tem credenciais
  próprias do lado de fora.
- Isso libera o projeto **a nível de infraestrutura GCP**. Não confundir
  com a segunda camada, interna do Hub: mesmo com o projeto liberado
  aqui, cada usuário do Hub só consegue efetivamente consultá-lo depois
  que um admin do Hub liberar esse `project_id` pra ele em `/admin`
  (ACL própria do Hub, [ADR-009](../adr/ADR-009-acl-usuario-projeto.md),
  ver [`docs/specs/admin.md`](../specs/admin.md)) — ou o projeto ser
  marcado como público em "Por projeto" → `hub_projects`. Este playbook
  cobre só a liberação de infraestrutura; a liberação de usuário é outro
  passo, feito depois, dentro do próprio Hub.

---

## 2. Decidir qual service account vai receber acesso

| Vai ser consultado por... | Service account a liberar |
|---|---|
| Uso real (Hub em produção) | `backend-run@observability-hub-prod.iam.gserviceaccount.com` |
| Teste interno (Hub em dev) | `backend-run@observability-hub-dev.iam.gserviceaccount.com` |

Se o mesmo projeto alvo vai ser usado tanto em teste quanto em produção,
rode os passos 3–4 duas vezes, uma por SA. Se o Hub foi hospedado em
outro par de projetos (ver o outro playbook,
[`hospedar-hub-em-novo-projeto.md`](hospedar-hub-em-novo-projeto.md)), o
e-mail da SA muda de acordo — confirme com
`gcloud iam service-accounts list --project=<projeto-do-hub>`.

---

## 3. Habilitar APIs no projeto alvo

```bash
gcloud services enable bigquery.googleapis.com logging.googleapis.com \
  --project={PROJECT_ID}
```

`logging.googleapis.com` é necessário mesmo sem intenção de gerar logs —
é o transporte que lineage (e o mapa de acesso) lê.

---

## 4. Conceder as 5 roles IAM à service account do Hub

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

Todos idempotentes — seguro rodar de novo. Resumo do que cada uma libera:

| Role | Pra quê |
|---|---|
| `bigquery.metadataViewer` | Catálogo (schemas/tabelas/colunas), freshness, descoberta de região |
| `bigquery.jobUser` | Rodar as queries acima (inclusive `INFORMATION_SCHEMA`, que roda como job) |
| `bigquery.dataViewer` | Profiling (amostragem, nulos, duplicatas, valores distintos) |
| `logging.viewer` | Chamar a API de Cloud Logging sem 403 — **sozinha não mostra Data Access audit logs**, ver linha abaixo |
| `logging.privateLogViewer` | Ver especificamente os Data Access audit logs (lineage, tabelas órfãs, mapa de acesso) |

> ⚠️ **A pegadinha mais cara de repetir:** `logging.viewer` sozinha não
> falha e não avisa nada — a API responde 200, só que a lista de eventos
> Data Access vem sempre vazia. Sem `logging.privateLogViewer` junto,
> lineage/tabelas órfãs parecem "sem atividade" mesmo com dados reais.
> As duas roles são obrigatórias **juntas**.

---

## 5. Habilitar Data Access audit logs do BigQuery

Só necessário se o cliente for usar **lineage, tabelas órfãs ou mapa de
acesso**. Sem isso, esses endpoints respondem `200 OK` com lista vazia —
não erra, só fica sempre sem dado.

**Via console (mais simples):** IAM & Admin → Audit Logs → localizar
"BigQuery API" → marcar "Data Read" e "Data Write" → Save.

**Via gcloud** (sempre leia a política atual antes de sobrescrever):

```bash
gcloud projects get-iam-policy {PROJECT_ID} --format=json > policy.json
# editar policy.json, mesclar (não substituir) o bloco abaixo em "auditConfigs"
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

---

## 6. Registrar e validar

1. **Registre a concessão** em
   [`docs/onboarding-cliente.md`](../onboarding-cliente.md), seção
   "Registro de acessos concedidos" (tabela: data, projeto alvo, SA,
   o que foi feito, confirmado via) — obrigatório por convenção do
   `CLAUDE.md` ("Registro de acessos e configurações"), antes de
   considerar a tarefa concluída.
2. **Confirme de verdade**, não assuma que o comando rodou:
   ```bash
   gcloud projects get-iam-policy {PROJECT_ID} \
     --flatten="bindings[].members" \
     --filter="bindings.members:backend-run@observability-hub-{dev,prod}.iam.gserviceaccount.com" \
     --format="table(bindings.role)"
   ```
3. **Teste pela UI do Hub**: logado como um usuário com acesso liberado
   a esse `project_id` (ver seção 1 acima sobre a camada de ACL do
   próprio Hub), digite o `project_id` no seletor. Se faltar alguma role
   de IAM, o erro (`ProjectAccessDeniedError`) já vem com os comandos de
   correção prontos. Se a IAM estiver certa mas o usuário não estiver
   autorizado no Hub, o erro é outro (`ProjectNotAuthorizedError`) e
   orienta pedir a um admin do Hub — não rodar `gcloud`.

---

## Checklist resumido

```
[ ] Decidido: SA de dev, de prod, ou as duas
[ ] bigquery.googleapis.com habilitada no projeto alvo
[ ] logging.googleapis.com habilitada no projeto alvo
[ ] roles/bigquery.metadataViewer concedida
[ ] roles/bigquery.jobUser concedida
[ ] roles/bigquery.dataViewer concedida
[ ] roles/logging.viewer concedida
[ ] roles/logging.privateLogViewer concedida (sem ela, logging.viewer
    sozinha NÃO mostra Data Access audit logs — falha silenciosa)
[ ] Data Access audit logs (DATA_READ + DATA_WRITE) habilitados —
    só se for usar lineage/tabelas órfãs/mapa de acesso
[ ] gcloud projects get-iam-policy confirmado (não só "rodei o comando")
[ ] Linha registrada em docs/onboarding-cliente.md
[ ] Testado na UI do Hub com um usuário já autorizado no ACL interno
```

---

## O que NÃO é necessário

- Nenhum agente, VM ou service account do lado do cliente — o Hub só lê
  via API, de fora do projeto.
- `roles/billing.viewer` / Cloud Billing — FinOps usa estimativa de custo
  via `INFORMATION_SCHEMA` + preço público do BigQuery, não Billing
  Export real (ver `docs/specs/finops-budget.md`).
- Secret Manager, Artifact Registry, Cloud Run, Firestore — recursos
  internos do Hub, vivem só em `observability-hub-{dev,prod}` (ou no par
  de projetos usado para hospedar o Hub), nunca no projeto alvo.

---

## Troubleshooting rápido

| Sintoma | Causa provável |
|---|---|
| 403 `ProjectAccessDeniedError` ao digitar o projeto no seletor | Falta alguma das 3 primeiras roles de BigQuery — a própria resposta já traz o comando |
| 403 `ProjectNotAuthorizedError` | IAM do GCP está OK, mas o usuário não está liberado no ACL interno do Hub — pedir a um admin do Hub, não rodar `gcloud` |
| Lineage/tabelas órfãs sempre "sem atividade", mesmo com dados reais | `logging.viewer` presente mas `logging.privateLogViewer` faltando — API responde 200, mas nunca mostra Data Access audit logs |
| Lineage responde 403 em vez de vazio | Falta `logging.viewer` (erro `LoggingAccessDeniedError`, já sugere as duas roles de logging juntas) |
| Tudo liberado mas ainda "sem atividade" | Confirmar se Data Access audit logs (seção 5) estão realmente habilitados — checar `auditConfigs` via `get-iam-policy`, não só assumir |

---

## Referências

- [ADR-006 — Modelo de acesso cross-project](../adr/ADR-006-cross-project.md)
- [ADR-009 — ACL de usuário × projeto](../adr/ADR-009-acl-usuario-projeto.md)
- [`docs/onboarding-cliente.md`](../onboarding-cliente.md) — checklist completo + registro vivo de concessões (fonte de verdade)
- [`docs/specs/admin.md`](../specs/admin.md) — como liberar um usuário do Hub para um `project_id` já autorizado a nível de infraestrutura
