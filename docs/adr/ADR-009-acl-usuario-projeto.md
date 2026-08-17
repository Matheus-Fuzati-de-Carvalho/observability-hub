# ADR-009 — Controle de acesso por usuário × projeto (ACL no Firestore)

**Status:** Aceito
**Data:** 2026-08-18

> **Nota de extensão (2026-08-20):** feedback de uso em produção da v1.0
> motivou três adições — coleção `hub_projects` (projeto liberado a
> todos, inclusive usuários futuros, eixo independente do
> `allowed_projects` de cada usuário), fluxo self-service de solicitação
> de acesso (`access_requests`) e mensagens de erro mais visíveis no
> frontend. Não é uma mudança de arquitetura — o modelo continua
> Firestore, leitura sempre fresca, gate via `require_project_access`/
> `require_admin`. Detalhe completo em
> [`docs/specs/admin.md`](../specs/admin.md) v1.1; esta decisão original
> não é revisada.

---

## Contexto

O modelo de acesso cross-project (ADR-006, "Modelo A") dá à service
account de runtime do Cloud Run acesso IAM a vários projetos GCP
alvo ao mesmo tempo — o caso de uso é consultoria, onde o Hub aponta
pra um projeto de cliente por vez, escolhido pelo usuário no seletor do
Topbar.

Isso cria um buraco de segurança quando o Hub serve **mais de um
cliente**: o único gate de acesso existente até aqui é
`Depends(get_current_user)` (`core/auth.py`), que valida só a sessão
(JWT de login via Google OAuth) — não valida se o usuário autenticado
deveria enxergar o `project_id` específico que ele digitou. Qualquer
usuário logado no Hub pode digitar qualquer `project_id` que a SA
alcance e ler os dados dele. Com 5+ projetos-cliente vinculados ao
mesmo Hub, um consultor alocado no Cliente A pode digitar o
`project_id` do Cliente B e ver dados dele — vazamento cross-cliente
real, não hipotético.

## Decisão

Adicionar uma segunda camada de autorização, **por usuário × projeto**,
em cima da autenticação existente — sem mexer no modelo de acesso da SA
ao GCP (ADR-006 continua válido e sem alteração).

- Coleção Firestore nova, `hub_users/{email}`
  (`is_admin: bool`, `allowed_projects: list[str]`, podendo conter o
  wildcard `"*"`) — ver [docs/specs/admin.md](../specs/admin.md) para o
  desenho completo.
- Nova dependency `core/auth.py::require_project_access`, que substitui
  `get_current_user` como gate de router em todo endpoint que recebe
  `project_id` como path param — 403 se o usuário não estiver
  autorizado, **antes** de qualquer chamada real ao BigQuery/Cloud
  Logging (mesmo que a SA tenha IAM lá).
- Tela de administração (`/admin`) dentro do próprio app, gated por uma
  segunda dependency (`require_admin`) baseada em `is_admin` no mesmo
  documento — sem senha nova, sem serviço novo.
- Allowlist de **login** (`OAUTH_ALLOWLIST`, Secret Manager) não muda —
  continua controlando só quem pode autenticar. Passar no login deixa
  de dar acesso implícito a projeto nenhum: acesso a `project_id` é
  sempre controlado pelo Firestore, à parte.

**Por que Firestore, não Secret Manager:** a SA de runtime já lê/escreve
Firestore hoje (favoritos, histórico) — nenhuma role de IAM nova. Uma
tela de admin precisa de escrita ao vivo (criar/editar/remover usuário);
Secret Manager é versionado e imutável por natureza (cada mudança é uma
versão nova), inadequado pra CRUD via UI, e já causou um problema real
de staleness nesta mesma sessão (`OAUTH_ALLOWLIST` cacheado com
`@lru_cache` sem TTL — instância quente do Cloud Run não pega mudança
até reiniciar). A checagem de ACL do Firestore é sempre uma leitura
fresca, sem cache, pra não repetir esse erro.

## Alternativas consideradas

**Afrouxar o problema pedindo IAM/OAuth por usuário (Modelo B do
ADR-006).** O Hub usaria o token do próprio usuário autenticado pra
consultar o BigQuery, herdando as permissões reais dele no GCP — mais
correto do ponto de vista de segurança (a fonte de verdade seria o IAM
do GCP, não uma allowlist paralela no Hub), mas o ADR-006 já rejeitou
essa opção por complexidade desproporcional ao estágio do produto
(exigiria OAuth com escopo de BigQuery + token forwarding). Continua
rejeitada aqui pelo mesmo motivo; se algum dia o produto crescer a
ponto de justificar, revisitar ADR-006 e esta decisão juntas.

**Guardar o ACL em variável de ambiente / arquivo estático versionado no
repositório.** Rejeitada — exigiria um deploy novo a cada mudança de
acesso (adicionar um consultor, revogar alguém), inviável pra uso
operacional real.

**Grupos do Google Workspace/IAM em vez de uma allowlist própria.** Mais
elegante em tese (delega a fonte de verdade pro GCP), mas exige
integração com Admin SDK/Cloud Identity e permissões administrativas
adicionais — desproporcional ao MVP. Documentado como possível evolução
futura, não descartada definitivamente.

## Consequências

- Todo endpoint de dado (catálogo, freshness, profiling, qualidade,
  lineage, PII, acesso, finops, validação de projeto) passa a exigir um
  registro explícito em `hub_users` além da sessão válida — **fail
  closed por padrão**: usuário sem registro não acessa projeto nenhum,
  mesmo que a SA tenha IAM lá.
- Requer um passo de bootstrap manual no primeiro deploy de cada
  ambiente (`scripts/seed_admin.py`, rodado com credenciais do
  operador) pra criar o primeiro administrador — sem isso, `hub_users`
  vazio bloqueia `/admin` também (ninguém é admin, ninguém consegue
  criar o primeiro registro pela UI). Documentado em
  `docs/specs/admin.md`, "Bootstrap do primeiro admin".
- Favoritos/histórico não passam pelo novo gate — só leem/escrevem a
  subárvore Firestore do próprio usuário (`users/{email}/...`), nunca
  disparam consulta real contra o projeto alvo.
- Se o Hub crescer para dezenas de clientes/times, o modelo
  usuário×projeto flat pode ficar trabalhoso de administrar (sem
  agrupamento por time/cliente) — aceito conscientemente para esta
  versão; grupos ficam como evolução futura se a dor aparecer de
  verdade.
