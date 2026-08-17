# Spec — Domínio: Admin (controle de acesso por usuário × projeto)

**Versão:** 1.0
**Status:** Aprovada
**Fase:** Transversal (não faz parte do roadmap de observabilidade de `docs/prd.md`) — plataforma
**Última atualização:** 2026-08-18

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

Ver [ADR-009](../adr/ADR-009-acl-usuario-projeto.md) para o contexto da
decisão arquitetural.

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
│   ├── admin.py                # novo — GET/PUT/DELETE users
│   └── auth.py                 # + is_admin em GET /me
├── core/
│   ├── auth.py                 # + require_admin, require_project_access
│   └── exceptions.py           # + ProjectNotAuthorizedError, AdminAccessRequiredError, LastAdminLockoutError
├── domains/
│   ├── admin/                  # novo domínio — schemas, repository, service
│   └── auth/schemas.py         # UserInfo + is_admin
└── tests/unit/
    ├── admin/                  # novo
    └── core/test_auth.py       # + require_admin/require_project_access

scripts/seed_admin.py           # novo — bootstrap do primeiro admin

apps/frontend/src/
├── components/ui/checkbox.tsx  # novo, via shadcn CLI
├── features/admin/             # novo — AdminPage, RequireAdmin, hooks
├── app/router.tsx              # + rota /admin, gated por RequireAdmin
├── app/topbar.tsx              # + link condicional (is_admin)
├── lib/http-client.ts          # + método put
└── types/auth.ts               # + is_admin
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
