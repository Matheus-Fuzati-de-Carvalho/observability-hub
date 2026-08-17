# Spec — Domínio: Admin (controle de acesso por usuário × projeto)

**Versão:** 1.1
**Status:** Aprovada
**Fase:** Transversal (não faz parte do roadmap de observabilidade de `docs/prd.md`) — plataforma
**Última atualização:** 2026-08-20

---

## Objetivo

Controle de acesso do Hub em duas camadas, administradas por uma tela
nova (`/admin`), sem senha nova e sem serviço novo — reaproveita 100% da
sessão Google OAuth já existente:

1. **Quem é administrador do Hub** — pode gerenciar a allowlist de
   acesso a projeto de outros usuários.
2. **A quais `project_id` cada usuário tem acesso** — o buraco de
   segurança real que motivou esta spec: até aqui, qualquer usuário
   autenticado podia digitar qualquer `project_id` no seletor do Topbar
   e ler dados dele, porque a service account de runtime tem IAM em
   vários projetos-cliente ao mesmo tempo (modelo cross-project do
   ADR-006) e a única barreira era `Depends(get_current_user)` — que só
   valida a sessão, não o projeto.

**Novo na v1.1** (feedback de uso da v1.0 em produção): mensagens de
erro mais visíveis, visão inversa projeto→usuários com opção de liberar
um projeto pra todo mundo (`hub_projects`), e um fluxo de solicitação de
acesso self-service (`access_requests`) — ver seções abaixo.

Ver [ADR-009](../adr/ADR-009-acl-usuario-projeto.md) para o contexto da
decisão arquitetural (não revisado nesta versão — a v1.1 é uma extensão
da mesma decisão, não uma mudança de arquitetura).

---

## Como se relaciona com o login (OAUTH_ALLOWLIST)

Login (**quem pode entrar no Hub**) continua controlado pelo secret
`OAUTH_ALLOWLIST` (Secret Manager, `domains/auth`) — domínio ou e-mail
específico, sem mudança nesta spec. O que muda: passar no login **não dá
mais acesso implícito a nenhum projeto**. Acesso a `project_id` é
sempre controlado por `hub_users/{email}` (Firestore, este domínio) —
um e-mail sem documento aqui loga normalmente, mas não vê dado de
nenhum projeto até um admin liberar.

---

## Fonte de dados

Coleção Firestore `hub_users/{email}` — documento único por e-mail,
mesmo mecanismo já usado por `domains/favorites`/`domains/history`
(a service account de runtime já tem leitura/escrita no Firestore do
próprio projeto, nenhuma role de IAM nova é necessária).

```json
{
  "email": "consultor.a@dp6.com.br",
  "is_admin": false,
  "allowed_projects": ["client-a-project", "client-b-project"],
  "created_at": "2026-08-18T10:00:00Z",
  "updated_at": "2026-08-18T10:00:00Z",
  "updated_by": "admin@dp6.com.br"
}
```

`allowed_projects` pode conter o literal `"*"`, que libera qualquer
`project_id` que a service account de runtime alcançar — para
admins/líderes que precisam ver todos os projetos-cliente de uma vez.

**Sem cache de leitura em nenhuma consulta** — leitura sempre fresca do
Firestore. O `@lru_cache` sem TTL de `core/secrets.py::get_oauth_allowlist`
já causou staleness real (instância quente do Cloud Run não pegava
mudança de allowlist até reiniciar); um controle de acesso que precisa
refletir revogação imediatamente não pode repetir esse erro.

---

## Projeto liberado a todos (`hub_projects`, v1.1)

Coleção `hub_projects/{project_id}` — eixo **independente** do
`allowed_projects` de cada usuário:

```json
{
  "project_id": "client-shared-project",
  "is_public": true,
  "created_at": "2026-08-20T10:00:00Z",
  "updated_at": "2026-08-20T10:00:00Z",
  "updated_by": "admin@dp6.com.br"
}
```

`is_public: true` libera o projeto pra **qualquer** usuário do Hub —
inclusive quem ainda não tem doc em `hub_users` (usuário futuro, criado
depois da liberação). `has_project_access` checa `hub_projects` primeiro,
antes de olhar o usuário:

```python
def has_project_access(client, email, project_id):
    project = repository.get_project(client, project_id)
    if project and project.get("is_public"):
        return True
    user = repository.get_user(client, email)
    if not user:
        return False
    allowed = user.get("allowed_projects", [])
    return "*" in allowed or project_id in allowed
```

A tela `/admin` → aba "Por projeto" é a visão inversa da aba "Por
usuário": em vez de editar um usuário e listar os projetos dele, o admin
escolhe um projeto e vê (e gerencia) quem tem acesso — via
`GET /admin/projects/{id}/users`, que consulta `hub_users` com
`array_contains_any [project_id, "*"]` (uma query só, sem escanear a
coleção inteira) e marca cada resultado como `granted_via: "explicit"`
ou `"wildcard"`.

---

## Solicitação de acesso (`access_requests`, v1.1)

Qualquer usuário autenticado (não precisa ser admin) pode pedir acesso a
uma lista de `project_id` — `POST /api/v1/access-requests` (fora do
prefixo `/admin`, de propósito: pedir acesso é exatamente o caso de uso
de quem ainda não tem acesso a nada). Cria um doc por `project_id` em
`access_requests/{auto_id}`:

```json
{
  "request_id": "abc123",
  "email": "consultor.b@dp6.com.br",
  "project_id": "client-c-project",
  "status": "pending",
  "requested_at": "2026-08-20T10:00:00Z",
  "resolved_at": null,
  "resolved_by": null
}
```

`create_access_requests` filtra automaticamente: pula `project_id` que
o usuário já tem acesso (`has_project_access`, já considera `hub_projects`
e wildcard) e pula `project_id` com pedido `pending` já existente do
mesmo usuário — nunca cria pedido redundante.

Admin vê pendências na aba "Solicitações" de `/admin` (mais um badge
discreto no ícone de admin do Topbar, com contador — `usePendingAccessRequests`
no frontend, `refetchInterval` de 60s, sem WebSocket) e aprova/nega:
`approve_access_request` concede o acesso de fato (mesma função
`grant_project_to_user` usada na aba "Por projeto") e marca
`status="approved"`; negar só marca `status="denied"`, sem conceder
nada.

---

## Duas dependencies novas em `core/auth.py`

```python
def require_admin(user=Depends(get_current_user), client=Depends(get_firestore_client)) -> UserInfo:
    """403 (AdminAccessRequiredError) se hub_users/{email}.is_admin != True."""

def require_project_access(project_id: str, user=Depends(get_current_user), client=Depends(get_firestore_client)) -> UserInfo:
    """403 (ProjectNotAuthorizedError) se project_id não estiver em
    hub_users/{email}.allowed_projects (nem "*" presente). Usuário sem
    documento tem allowed_projects vazio -> nega tudo (fail closed)."""
```

`require_project_access` substitui `get_current_user` como dependency de
router em **todo** endpoint que recebe `project_id` como path param:
`catalog`, `freshness`, `profiling`, `quality`, `lineage`, `pii`,
`access`, `finops`, `projects` (inclusive `GET /projects/{id}/validate`,
o primeiro endpoint chamado quando o usuário digita um projeto no
seletor — barra ali, antes de qualquer outra tela). `favorites`/`history`
não mudam: `project_id` ali só aparece como escopo do próprio doc do
usuário (`users/{email}/favorites/...`), nunca dispara consulta real
contra o projeto alvo.

Distinção importante de mensagem de erro:
- `ProjectAccessDeniedError` (já existia) — a service account não tem
  IAM no GCP; orienta rodar `gcloud add-iam-policy-binding`.
- `ProjectNotAuthorizedError` (nova) — a SA pode até ter IAM, mas o
  **usuário não está autorizado no ACL do Hub**; orienta pedir a um
  admin do Hub, não rodar `gcloud`.

---

## Endpoints da API

Todos sob `dependencies=[Depends(require_admin)]` — 403
(`AdminAccessRequiredError`) para quem não é admin.

### GET /api/v1/admin/users
Lista todos os `hub_users`, ordenados por e-mail.

### PUT /api/v1/admin/users/{email}
Upsert (cria se não existe, atualiza se existe). `created_at` é
preservado em updates.

**Body:**
```json
{"is_admin": false, "allowed_projects": ["client-a-project"]}
```

### DELETE /api/v1/admin/users/{email}
Remove o documento (idempotente — deletar e-mail inexistente não é
erro). Não afeta a allowlist de **login** — só remove acesso a projeto
e/ou status de admin.

Ambos `PUT`/`DELETE` bloqueiam remover `is_admin` (ou deletar) do
**último** administrador restante (`LastAdminLockoutError`, HTTP 400) —
sem isso, ninguém mais conseguiria abrir `/admin` pra reverter.

### GET /api/v1/admin/projects
Lista `hub_projects`, ordenados por `project_id`.

### PUT /api/v1/admin/projects/{project_id}
Upsert — cria o projeto (registra pra aparecer na aba "Por projeto") ou
atualiza `is_public`. Body: `{"is_public": true}`.

### GET /api/v1/admin/projects/{project_id}/users
Quem tem acesso a este projeto — `is_public` + lista de
`{email, is_admin, granted_via}` (explícito ou wildcard). Não lista
"todo mundo" quando `is_public=true` (é uma população não-finita, não
uma lista de e-mails).

### POST /api/v1/admin/projects/{project_id}/users/{email}
Concede — idempotente, cria o usuário (`is_admin=False`) se ainda não
existir, adiciona `project_id` à lista dele preservando o resto.

### DELETE /api/v1/admin/projects/{project_id}/users/{email}
Revoga — remove só este `project_id` da lista do usuário. **Não afeta**
`hub_projects.is_public`: se o projeto está público, o usuário continua
acessando por esse eixo independente mesmo depois da revogação explícita.

### GET /api/v1/admin/access-requests?status=pending
Lista `access_requests`, mais recente primeiro. `status` opcional
(`pending`/`approved`/`denied`); sem o parâmetro, lista todas.

### POST /api/v1/admin/access-requests/{request_id}/approve
Concede o projeto (via `grant_project_to_user`) e marca `status="approved"`.
404 (`AccessRequestNotFoundError`) se `request_id` não existir.

### POST /api/v1/admin/access-requests/{request_id}/deny
Só marca `status="denied"` — não concede nada.

### POST /api/v1/access-requests (fora de `/admin`, qualquer usuário autenticado)
Cria pedidos pra si mesmo. Body: `{"project_ids": ["proj-a", "proj-b"]}`.
Filtra silenciosamente projetos já acessíveis ou com pedido pendente
duplicado — ver "Solicitação de acesso" acima.

---

## `is_admin` exposto só em `GET /auth/me`

`UserInfo` (payload do JWT de sessão) ganhou o campo `is_admin: bool = False`,
mas **só `GET /auth/me` o popula de verdade** (uma leitura Firestore
extra, só nessa rota). `get_current_user` (usado em todo request
autenticado) não ganha I/O novo — seria desperdício ler Firestore em
toda chamada de catálogo/freshness/etc. quando só o frontend, ao montar
a sessão, precisa saber se mostra o link de admin.

**Consequência de design:** `user.is_admin` só é confiável quando o
`UserInfo` vem de `/auth/me`. `require_admin` nunca confia nesse campo —
sempre faz sua própria checagem fresca no Firestore.

---

## Bootstrap do primeiro admin

No primeiro deploy, `hub_users` está vazio → `require_project_access`
nega todo `project_id` pra todo mundo (fail closed, esperado) e
`require_admin` nega `/admin` pra todo mundo — ninguém consegue criar o
primeiro registro pela UI (problema de ovo-e-galinha). Resolvido com
`scripts/seed_admin.py` (credenciais do operador via
`gcloud auth application-default login`, não a SA de runtime):

```bash
cd apps/backend
uv run python ../../scripts/seed_admin.py --project observability-hub-dev --email <primeiro-admin>
```

Rodar em dev primeiro, validar o fluxo ponta a ponta, só depois em prod.

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   ├── admin.py                # GET/PUT/DELETE users + projects + access-requests
│   ├── access_requests.py      # novo (v1.1) — POST público, fora de /admin
│   └── auth.py                 # + is_admin em GET /me
├── core/
│   ├── auth.py                 # require_admin, require_project_access
│   └── exceptions.py           # ProjectNotAuthorizedError, AdminAccessRequiredError,
│                                # LastAdminLockoutError, AccessRequestNotFoundError (v1.1)
├── domains/
│   ├── admin/                  # schemas, repository, service — hub_users + hub_projects (v1.1)
│   │                           # + access_requests (v1.1)
│   └── auth/schemas.py         # UserInfo + is_admin
└── tests/unit/
    ├── admin/
    └── core/test_auth.py       # require_admin/require_project_access

scripts/seed_admin.py           # bootstrap do primeiro admin

apps/frontend/src/
├── components/
│   ├── ui/checkbox.tsx         # via shadcn CLI
│   └── ApiErrorNotice.tsx      # + prop `action` (v1.1) — CTA opcional junto da mensagem
├── features/
│   ├── admin/
│   │   ├── AdminPage.tsx        # shell de abas (v1.1): Por usuário / Por projeto / Solicitações
│   │   ├── AdminUsersTab.tsx    # conteúdo da v1.0, extraído (v1.1)
│   │   ├── AdminProjectsTab.tsx # novo (v1.1) — visão projeto -> usuários + is_public
│   │   ├── AdminAccessRequestsTab.tsx  # novo (v1.1)
│   │   ├── ProjectChipEditor.tsx       # novo (v1.1) — compartilhado
│   │   ├── RequestAccessDialog.tsx     # novo (v1.1)
│   │   ├── RequireAdmin.tsx
│   │   └── hooks.ts
│   └── projects/ProjectSelector.tsx    # erro visível + CTA "Solicitar acesso" (v1.1)
├── app/
│   ├── router.tsx               # rota /admin, gated por RequireAdmin
│   ├── topbar.tsx                # link + badge de pendentes (v1.1) + botão "Solicitar acesso"
│   └── layout.tsx                # CTA "Solicitar acesso" no estado vazio (v1.1)
├── lib/
│   ├── http-client.ts            # + método put
│   └── api/accessRequests.ts     # novo (v1.1)
└── types/
    ├── auth.ts                   # + is_admin
    └── admin.ts                  # + HubProject, AccessRequest, etc. (v1.1)
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Usuário sem doc em `hub_users` | Loga normalmente (login é allowlist de domínio/email, separado) mas `allowed_projects` vazio → `ProjectNotAuthorizedError` em qualquer projeto |
| `"*"` em `allowed_projects` | Acesso a qualquer `project_id` que a SA de runtime alcançar |
| Remover `is_admin` (ou deletar) do último admin | Bloqueado (`LastAdminLockoutError`, 400) |
| `DELETE` de e-mail inexistente | Idempotente, 204 |
| E-mail digitado com maiúsculas no formulário de admin | Normalizado pra lowercase em `service.py` antes de gravar/consultar |
| Primeiro deploy, `hub_users` vazio | Fail closed total (login funciona, nenhum projeto acessível, `/admin` inacessível) até rodar `scripts/seed_admin.py` |
| SA tem IAM no projeto mas usuário não tem ACL no Hub | `ProjectNotAuthorizedError` (403) — nunca chega a tentar a query real no BigQuery |
| `hub_projects/{id}.is_public = true` | Libera geral, inclusive usuário sem doc em `hub_users` — checado antes de qualquer coisa em `has_project_access` |
| Solicitar acesso a projeto que já tem (explícito, wildcard ou público) | Filtrado silenciosamente pelo backend, não cria pedido |
| Solicitar acesso a projeto com pedido `pending` já existente do mesmo usuário | Filtrado, não duplica |
| Aprovar pedido de projeto que virou público nesse meio-tempo | `grant_project_to_user` roda normalmente (idempotente — resultado final é o mesmo) |
| Revogar (`DELETE .../projects/{id}/users/{email}`) o único acesso explícito de alguém a um projeto público | Sem efeito real — o projeto continua público, `is_public` não muda por essa chamada (eixos independentes) |
| `request_id` inexistente em approve/deny | 404 (`AccessRequestNotFoundError`) |

---

## Fora do escopo desta spec

- **Gerenciar a allowlist de login (`OAUTH_ALLOWLIST`)** pela tela de
  admin — continua manual via `gcloud secrets versions add`, como hoje.
  Escreve-la exigiria conceder `secretmanager.versions.add` à SA de
  runtime, uma permissão mais sensível que Firestore read/write (que a
  SA já tem); decisão consciente de manter o escopo desta v1 menor.
- **Histórico/audit log de mudanças de ACL** — `updated_by`/`updated_at`
  no próprio documento cobrem "quem mudou por último", não um log
  completo de mudanças ao longo do tempo.
- **Expiração automática de acesso** (ex: acesso temporário por N dias)
  — todo acesso concedido é permanente até um admin revogar manualmente.
- **Grupos/times** (ex: liberar todos os projetos de um "time Cliente A"
  de uma vez) — hoje é sempre usuário × projeto, sem agrupamento.
- **Tela de acompanhamento do próprio usuário** ("minhas solicitações")
  — só o admin vê/gerencia `access_requests`; quem solicita só recebe a
  confirmação de envio no momento, sem histórico de status depois.
- **Notificação por e-mail** ao aprovar/negar uma solicitação — só
  reflete dentro do Hub (badge de pendentes some da visão do admin; o
  solicitante percebe na próxima vez que tentar acessar o projeto).
