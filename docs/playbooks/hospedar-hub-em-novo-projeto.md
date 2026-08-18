# Playbook — Hospedar o Observability Hub em um novo par de projetos GCP

**Pergunta que este playbook responde:** "quero rodar minha própria cópia
do Hub — hospedagem e administração — em projetos GCP diferentes dos
`observability-hub-dev`/`observability-hub-prod` originais. O que precisa
ser feito, do zero, pra outra pessoa replicar isto?"

Este é um playbook de **bootstrap único por par de ambientes** — a
maioria dos passos roda uma vez (ou duas, dev depois prod) e nunca mais.
Depois de concluído, o dia a dia é só `git push` (ver CLAUDE.md, "CI/CD e
deploy").

Não confundir com o outro playbook,
[`liberar-projeto-para-o-hub.md`](liberar-projeto-para-o-hub.md) — aquele
é sobre liberar acesso a um projeto *que o Hub vai observar*; este é
sobre onde o Hub *em si* roda.

---

## 1. Visão geral do que vai existir no final

Um par de projetos GCP (`dev` e `prod`, nunca compartilham recursos —
ver `CLAUDE.md`, Guardrails), cada um com:

- 2 serviços Cloud Run (`backend` FastAPI, `frontend` React estático)
- 1 repositório Artifact Registry (`apps`) compartilhado pelos dois
- 1 service account de runtime por serviço (`backend-run`, `frontend-run`)
- Firestore (Native mode) — dado próprio do Hub: ACL de usuário×projeto,
  favoritos, histórico, login events
- Secret Manager — credenciais OAuth, JWT, allowlist de login
- Workload Identity Federation — GitHub Actions autentica sem chave de
  service account
- 1 bucket GCS de remote state do Terraform

```
GitHub (push) → GitHub Actions (WIF, sem chave) → Terraform apply
                                                  → build + push imagem
                                                  → gcloud run deploy
```

`dev` recebe push de qualquer branch exceto `main`; `prod` recebe
push/merge em `main` (ver `CLAUDE.md`, "CI/CD e deploy").

---

## 2. Pré-requisitos

- `gcloud` CLI instalado e autenticado (`gcloud auth login` +
  `gcloud auth application-default login`) com uma conta que seja Owner
  (ou papéis equivalentes: Project IAM Admin, Service Usage Admin,
  Storage Admin, Workload Identity Pool Admin, Service Account Admin) —
  vai criar os projetos do zero.
- Terraform `>= 1.7` (o pipeline usa `1.9.8`, ver `.github/workflows/`).
- Uma conta de billing do GCP para vincular aos dois projetos novos.
- Um repositório GitHub próprio (fork ou cópia deste repo) — o WIF é
  restrito a `owner/repo` exato, então o valor precisa ser o do seu
  repositório, não o original.
- `gh` CLI autenticado nesse repositório (só necessário se for usar os
  comandos `gh secret set` abaixo — pode ser feito pela UI do GitHub também).

---

## 3. Escolher os nomes dos projetos

Este repositório, como está hoje, **hardcoda** `observability-hub-dev` e
`observability-hub-prod` em vários lugares (não é parametrizado via
`.tfvars` em CI — os `terraform.tfvars.example` existem só como
referência para apply manual local). Escolha os dois `project_id` novos
agora — todo o restante deste playbook assume que você já decidiu os
dois nomes (ex: `acme-hub-dev` / `acme-hub-prod`) e vai substituí-los
consistentemente nos arquivos listados no passo 6.

> ⚠️ **Requisito obrigatório, não só convenção**: os dois `project_id`
> precisam terminar literalmente em `-dev` e `-prod` (ex:
> `acme-hub-dev`/`acme-hub-prod`, `qualquercoisa-dev`/`qualquercoisa-prod`
> — o prefixo é livre, o sufixo não). `apps/backend/src/observability_hub/
> core/secrets.py::_is_prod()` decide qual par de secrets OAuth ler
> (`GOOGLE_OAUTH_CLIENT_ID_DEV` vs. `_PROD`) checando literalmente se
> `project_id.endswith("-prod")` — é o único lugar do código que depende
> disso, mas se os nomes escolhidos não seguirem esse padrão (ex:
> `acme-homologacao`/`acme-producao`), o backend de "prod" vai
> silenciosamente ler os secrets de "_DEV" pra sempre, sem erro nenhum, e
> o login vai falhar de um jeito confuso de debugar. Não é negociável —
> escolha nomes terminados em `-dev`/`-prod`.

---

## 4. Criar os projetos GCP e vincular billing

```bash
gcloud projects create {NOVO_PROJETO_DEV} --name="Observability Hub (dev)"
gcloud projects create {NOVO_PROJETO_PROD} --name="Observability Hub (prod)"

gcloud billing projects link {NOVO_PROJETO_DEV} --billing-account={BILLING_ACCOUNT_ID}
gcloud billing projects link {NOVO_PROJETO_PROD} --billing-account={BILLING_ACCOUNT_ID}
```

`{BILLING_ACCOUNT_ID}` — descubra com `gcloud billing accounts list`.

---

## 5. Habilitar e provisionar o Firestore (passo manual — não é Terraform hoje)

Nenhum módulo Terraform deste repositório cria banco Firestore
(`infra/terraform/modules/` ainda não tem um módulo de Firestore/dado
próprio — só `cloud-run` está escrito; ver `CLAUDE.md`). O backend
(`domains/admin`, `favorites`, `history`) só funciona se o banco existir.
Faça isso agora, uma vez por projeto, **antes** do primeiro deploy do
backend:

```bash
gcloud services enable firestore.googleapis.com --project={PROJETO}

gcloud firestore databases create \
  --project={PROJETO} \
  --location={REGIAO_FIRESTORE} \
  --type=firestore-native
```

`{REGIAO_FIRESTORE}` precisa ser uma
[localização Firestore válida](https://cloud.google.com/firestore/docs/locations)
— `us-central1` funciona como região regular (o mesmo valor usado como
`region` no resto deste playbook). Repita para os dois projetos.

---

## 6. Ajustar os defaults do repositório para os novos projetos

Edite estes arquivos, trocando `observability-hub-dev`/`-prod` pelos
nomes escolhidos no passo 3 (e o `github_repository` pelo seu
`owner/repo`):

| Arquivo | O que trocar |
|---|---|
| `infra/terraform/bootstrap/dev/variables.tf` | `default` de `project_id`, `default` de `github_repository` |
| `infra/terraform/bootstrap/prod/variables.tf` | idem, para prod |
| `infra/terraform/environments/dev/variables.tf` | `default` de `project_id` |
| `infra/terraform/environments/prod/variables.tf` | `default` de `project_id` |
| `infra/terraform/environments/dev/versions.tf` | `backend "gcs" { bucket = "..." }` → `{NOVO_PROJETO_DEV}-tfstate` |
| `infra/terraform/environments/prod/versions.tf` | idem, `{NOVO_PROJETO_PROD}-tfstate` |
| `.github/workflows/backend-deploy-dev.yml` | `env.PROJECT_ID` |
| `.github/workflows/backend-deploy-prod.yml` | `env.PROJECT_ID` |
| `.github/workflows/frontend-deploy-dev.yml` | `env.PROJECT_ID` |
| `.github/workflows/frontend-deploy-prod.yml` | `env.PROJECT_ID` |

O nome do bucket de state (`versions.tf`) precisa bater exatamente com o
que o bootstrap vai criar no passo 7 (`<project_id>-tfstate`, ver
`infra/terraform/bootstrap/modules/wif-bootstrap/main.tf`).
`docs/onboarding-cliente.md` também cita os `project_id` originais como
exemplo — não é funcional, mas vale revisar depois pra não confundir
quem ler.

---

## 7. Bootstrap do Terraform (uma vez por ambiente, fora do CI)

Já documentado em detalhe em
[`infra/terraform/bootstrap/README.md`](../../infra/terraform/bootstrap/README.md)
— resumo aqui, siga o README para o passo a passo completo:

```bash
cd infra/terraform/bootstrap/dev
terraform init
terraform plan
terraform apply

cd ../prod
terraform init
terraform plan
terraform apply
```

Isso cria, por projeto: bucket de state, as APIs base habilitadas
(`iam`, `run`, `artifactregistry`, `bigquery`, `secretmanager`,
`logging`, etc. — lista completa em
`infra/terraform/bootstrap/modules/wif-bootstrap/main.tf`), o pool/
provider de Workload Identity Federation, e a service account de deploy
(`gh-deploy-{dev,prod}`).

**Guarde o `terraform.tfstate` local destes dois diretórios fora do
Git** (não é versionado, é a única cópia) — o README já avisa, reforçando
aqui porque é fácil perder numa máquina descartável.

Ao final, capture os três outputs de cada ambiente:

```bash
terraform output state_bucket_name
terraform output workload_identity_provider
terraform output service_account_email
```

---

## 8. Configurar os secrets do GitHub Actions e o gate de aprovação de prod

Quatro secrets no repositório (Settings → Secrets and variables →
Actions), usando os outputs do passo 7:

```bash
gh secret set WIF_PROVIDER_DEV --body "<workload_identity_provider de dev>"
gh secret set WIF_SA_DEV --body "<service_account_email de dev>"
gh secret set WIF_PROVIDER_PROD --body "<workload_identity_provider de prod>"
gh secret set WIF_SA_PROD --body "<service_account_email de prod>"
```

Sem isso, todo workflow falha no primeiro passo (`google-github-actions/auth`).

### 8.1 Gate de aprovação manual em prod (não é opcional — os workflows já esperam por ele)

Desde 2026-08-18, `backend-deploy-prod.yml` e `frontend-deploy-prod.yml`
declaram `environment: production` no job de deploy (ver `CLAUDE.md`,
"CI/CD e deploy") — deploy de app em prod não roda mais sozinho a cada
push em `main`, ele fica **parado em "Waiting"** até alguém aprovar.
Isso é só metade da configuração: o outro lado é um **GitHub Environment**
chamado exatamente `production`, com "required reviewers", que precisa
ser criado nas *Settings* deste novo repositório (não é algo que o
Terraform ou o código gerencia):

1. **Settings → Environments → New environment**
2. Nome: **`production`** (exatamente esse nome — é o que os workflows
   referenciam)
3. Marque **"Required reviewers"** e adicione quem deve aprovar deploys
   de prod
4. Save protection rules

Se você pular este passo, os workflows continuam funcionando — só que
**sem gate nenhum**: `environment: production` sem uma regra de proteção
configurada não bloqueia nada, o job roda direto. `terraform-apply-
prod.yml` (aplica infra) continua automático de propósito, mesmo com
esse gate configurado — só os dois deploys de app são afetados (decisão
consciente, ver `CLAUDE.md`).

---

## 9. Primeiro apply do Terraform de ambiente

Com os arquivos do passo 6 já commitados, dê push numa branch qualquer
(não `main`) tocando `infra/terraform/environments/dev/**` — isso
dispara `terraform-apply-dev.yml` automaticamente. Confirme que rodou
com sucesso (`gh run list --workflow=terraform-apply-dev.yml`) antes de
seguir — ele cria os dois serviços Cloud Run (`backend`, `frontend`) com
uma imagem placeholder pública, o repositório Artifact Registry e as
service accounts de runtime.

Para prod, o mesmo `terraform apply` só roda em push/merge para `main` —
deixe para depois de validar tudo em dev (passo 15).

Alternativa manual (se preferir não depender do primeiro push para
isso): `cd infra/terraform/environments/dev && terraform init && terraform apply`,
autenticado com as mesmas credenciais de Owner do passo 2.

---

## 10. Conceder as roles manuais à service account de runtime do backend

O módulo `cloud-run` cria a service account (`backend-run@{projeto}...`)
mas **não concede nenhuma role própria** ainda (comentário no próprio
`main.tf` do módulo: "hoje sem papéis próprios"). Sem isso, o backend
sobe mas todo endpoint que toca Firestore ou Secret Manager falha em
runtime. Rode para os dois projetos:

```bash
SA_EMAIL="backend-run@{PROJETO}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding {PROJETO} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/datastore.user"

gcloud projects add-iam-policy-binding {PROJETO} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/secretmanager.secretAccessor"
```

Essas duas roles são **só no próprio projeto** — nunca pedidas a um
projeto alvo (ver `docs/onboarding-cliente.md`, "O que NÃO é necessário").

---

## 11. Configurar o OAuth Client no Google Cloud Console

O login usa Google OAuth (`domains/auth`), escopo `openid email profile`
— não é um escopo sensível, então não precisa de revisão de verificação
do Google mesmo publicando a tela de consentimento como "Externo/Em
produção".

1. **APIs & Services → OAuth consent screen**: crie a tela (tipo Interno
   se seu Google Workspace cobrir todos os usuários esperados; Externo
   caso contrário — publique como "Em produção" para não cair no limite
   de 100 usuários de teste). Escopos: `openid`, `email`, `profile`.
2. **APIs & Services → Credentials → Create Credentials → OAuth client
   ID**, tipo "Web application", um client por ambiente (dev e prod usam
   client IDs diferentes — `secrets.py` já espera isso, ver passo 12).
3. **Authorized redirect URIs** — a URL do **frontend** (não do backend)
   + `/auth/callback`. Pegue as duas URLs válidas do serviço criado no
   passo 9:
   ```bash
   gcloud run services describe frontend --project={PROJETO} --region={REGIAO} \
     --format='value(status.url)'
   ```
   mais a URL alternativa por número do projeto (ver output
   `service_url_alt` do módulo `cloud-run`,
   `https://frontend-{numero_do_projeto}.{regiao}.run.app`). Cadastre as
   duas, para dev e para prod (4 URIs no total, 2 por client).
4. Anote o **Client ID** e o **Client Secret** gerados — vão para o
   Secret Manager no próximo passo.

---

## 12. Criar os secrets no Secret Manager

Cinco secrets, por projeto (`GOOGLE_OAUTH_CLIENT_ID_{DEV,PROD}` e
`GOOGLE_OAUTH_CLIENT_SECRET_{DEV,PROD}` mudam de sufixo conforme o
ambiente — mesmo nome e valor esperado nos dois projetos onde fizer
sentido; `core/secrets.py` decide qual ler pelo próprio nome do projeto
rodando, ver o sufixo `-dev`/`-prod` do `project_id`):

```bash
# em observability-hub-dev (ou o nome novo escolhido)
echo -n "{CLIENT_ID_DEV}"     | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID_DEV --data-file=- --project={PROJETO_DEV}
echo -n "{CLIENT_SECRET_DEV}" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET_DEV --data-file=- --project={PROJETO_DEV}
echo -n "{JWT_SECRET_ALEATORIO}" | gcloud secrets create JWT_SECRET --data-file=- --project={PROJETO_DEV}
echo -n '{"allowed_domains": ["seudominio.com"], "allowed_emails": []}' \
  | gcloud secrets create OAUTH_ALLOWLIST --data-file=- --project={PROJETO_DEV}

# em observability-hub-prod (ou o nome novo escolhido)
echo -n "{CLIENT_ID_PROD}"     | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID_PROD --data-file=- --project={PROJETO_PROD}
echo -n "{CLIENT_SECRET_PROD}" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET_PROD --data-file=- --project={PROJETO_PROD}
echo -n "{JWT_SECRET_ALEATORIO_DIFERENTE}" | gcloud secrets create JWT_SECRET --data-file=- --project={PROJETO_PROD}
echo -n '{"allowed_domains": ["seudominio.com"], "allowed_emails": []}' \
  | gcloud secrets create OAUTH_ALLOWLIST --data-file=- --project={PROJETO_PROD}
```

Notas:
- `JWT_SECRET`: gere um valor aleatório longo por ambiente (ex:
  `openssl rand -hex 32`) — **use valores diferentes em dev e prod**,
  nunca o mesmo segredo nos dois.
- `OAUTH_ALLOWLIST` é quem entra no Hub (login), não quem acessa qual
  projeto — controla só a barreira inicial. Ajuste `allowed_domains`/
  `allowed_emails` para a realidade de quem vai usar o Hub.
- `secrets.py` lê sempre a versão `latest`, cacheada por processo
  (`lru_cache`) — atualizar um secret exige reiniciar as instâncias do
  Cloud Run (ou aguardar novo deploy/scale) para o valor novo valer.
- Nenhum desses secrets é gerenciado por Terraform hoje
  (`infra/terraform/modules/secret-manager/` ainda é um módulo vazio) —
  são só os `gcloud secrets create` acima, manuais.

---

## 13. Deploy real do backend e frontend

Os workflows `backend-deploy-dev.yml`/`frontend-deploy-dev.yml` só têm
gatilho `on: push` filtrado por path (`apps/backend/**`/`apps/frontend/**`)
— sem `workflow_dispatch`, não dá para disparar manualmente pela UI/`gh
workflow run`. Se o push do passo 9 alterou só os arquivos de
`infra/terraform/**` (caso comum ao replicar: você editou só os 10
arquivos do passo 6, sem tocar código de app), esses dois workflows
**não disparam sozinhos**. Garanta que eles rodem pelo menos uma vez —
o jeito mais simples é incluir qualquer alteração trivial em
`apps/backend/**`/`apps/frontend/**` no mesmo push (ou num push logo
em seguida), nem que seja um comentário.

Quando disparam, eles buildam a imagem, dão push no Artifact Registry e
rodam `gcloud run deploy --image ...`. O frontend builda com
`VITE_API_BASE_URL` apontando pra URL real do backend, descoberta em
runtime do workflow via `gcloud run services describe backend` — não
precisa configurar isso manualmente.

Confirme:

```bash
gh run list --workflow=backend-deploy-dev.yml --limit=1
gh run list --workflow=frontend-deploy-dev.yml --limit=1
```

---

## 14. Bootstrap do primeiro administrador

Sem isso, `hub_users` fica vazio e ninguém consegue abrir `/admin` —
nem `require_admin` nem `require_project_access` liberam nada sem
documento existente (fail closed por design). Rode localmente, com suas
credenciais de operador (não a service account de runtime):

```bash
gcloud auth application-default login   # se ainda não tiver feito

cd apps/backend
uv run python ../../scripts/seed_admin.py \
  --project {PROJETO_DEV} --email {seu-email-admin}
```

Rode em dev primeiro, valide o fluxo ponta a ponta, só depois repita
para `{PROJETO_PROD}`.

---

## 15. Validar ponta a ponta (dev)

1. Abra a URL do frontend de dev no navegador.
2. Clique em "Entrar com Google", autentique com um e-mail coberto pelo
   `OAUTH_ALLOWLIST` do passo 12.
3. Confirme que o login completa (senão, ver Troubleshooting abaixo).
4. Se o e-mail usado foi o mesmo do `seed_admin.py` (passo 14), confirme
   que o link/ícone de administrador aparece e `/admin` abre.
5. Digite um `project_id` no seletor — nesse ponto, nenhum projeto alvo
   foi liberado ainda (isso é o outro playbook,
   [`liberar-projeto-para-o-hub.md`](liberar-projeto-para-o-hub.md)), então
   espera-se um erro `ProjectNotAuthorizedError`/`ProjectAccessDeniedError`
   — é o sinal de que a stack está de pé e o gate de ACL está funcionando.

---

## 16. Repetir para prod

Depois de validar dev:

1. Merge/push da branch com os arquivos do passo 6 para `main` — dispara
   `terraform-apply-prod.yml` (cria os serviços Cloud Run de prod,
   automático) e, em seguida, `backend-deploy-prod.yml`/
   `frontend-deploy-prod.yml`.
2. **Os dois deploys de app ficam em "Waiting"** se o passo 8.1 foi
   configurado — abra a aba *Actions* do repositório, clique no run
   parado, **Review deployments → Approve and deploy**. Sem isso os dois
   jobs nunca terminam (não é erro, é o gate funcionando).
3. Repita os passos 10 (roles manuais), 11 (OAuth client de prod — client
   **separado** do de dev), 12 (secrets `_PROD`) e 14 (seed do primeiro
   admin) apontando para `{PROJETO_PROD}`.
4. Repita a validação do passo 15 na URL de prod.

---

## 17. Depois de hospedado

O Hub está de pé, mas ainda não observa nenhum dado — ele só enxerga
projetos GCP explicitamente liberados. Para cada projeto que ele deve
observar (incluindo, se quiser, os próprios `{PROJETO_DEV}`/`{PROJETO_PROD}`
servindo de alvo um do outro, como o par original faz), siga
[`liberar-projeto-para-o-hub.md`](liberar-projeto-para-o-hub.md).

---

## Checklist final

```
[ ] project_id de dev e prod escolhidos terminando literalmente em
    "-dev"/"-prod" (obrigatório, ver passo 3 — não só convenção)
[ ] Projetos GCP criados e billing vinculado (dev + prod)
[ ] Firestore Native mode provisionado nos dois projetos
[ ] Arquivos do passo 6 editados e commitados (project_id, bucket de
    state, github_repository, PROJECT_ID dos 4 workflows)
[ ] Bootstrap Terraform aplicado manualmente (dev + prod) — outputs
    capturados
[ ] 4 secrets do GitHub Actions configurados (WIF_PROVIDER_DEV/PROD,
    WIF_SA_DEV/PROD)
[ ] Environment "production" criado nas Settings do GitHub com
    required reviewers (passo 8.1) — sem isso os deploys de app em prod
    não têm gate nenhum
[ ] Primeiro apply de environments/dev confirmado com sucesso
[ ] roles/datastore.user + roles/secretmanager.secretAccessor concedidas
    à backend-run em cada projeto
[ ] OAuth consent screen + OAuth Client (dev e prod, client IDs
    diferentes) configurados com os redirect URIs corretos
[ ] 5 secrets por ambiente criados no Secret Manager
    (GOOGLE_OAUTH_CLIENT_ID/SECRET, JWT_SECRET, OAUTH_ALLOWLIST)
[ ] Deploy de backend e frontend confirmado (dev)
[ ] Primeiro admin criado via scripts/seed_admin.py (dev)
[ ] Login + /admin validados ponta a ponta em dev
[ ] Passos 9–14 repetidos para prod
[ ] Deploys de app em prod aprovados manualmente (Review deployments),
    se o gate do passo 8.1 estiver configurado
[ ] Login + /admin validados ponta a ponta em prod
```

---

## Troubleshooting

Baseado em incidentes reais já registrados em `CHANGELOG.md` (Fase 1):

| Sintoma | Causa | Correção |
|---|---|---|
| `terraform apply` do bootstrap falha criando a SA de runtime (`iam.serviceAccounts.create denied`) | Faltou `roles/iam.serviceAccountAdmin` na SA de deploy | Já corrigido no módulo `wif-bootstrap` deste repo — se você clonou uma versão anterior, adicione a role manualmente à `gh-deploy-{env}` e reaplique o bootstrap |
| Cloud Run criado "fora do state" do Terraform, com a SA default do Compute Engine em vez de `backend-run` | `terraform-apply-*.yml` e `backend-deploy-*.yml` rodaram em paralelo no mesmo push, e o deploy criou o serviço antes do Terraform | Os workflows deste repo já têm `wait-for-terraform` para isso — não remova esse job ao adaptar os workflows |
| Drift entre o Cloud Run real e o state do Terraform | Consequência do item acima, se já tiver acontecido | Em ambiente sem tráfego real: `gcloud run services delete` seguido de `terraform apply`. Com tráfego real, preferir `terraform import` |
| Provider `google` falha no primeiro `terraform apply` do bootstrap reclamando de Service Usage/Resource Manager API desabilitada | Em alguns projetos novíssimos essas duas não vêm habilitadas por padrão | `gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com --project={PROJETO}` antes do primeiro apply |
| Backend sobe mas todo endpoint autenticado falha (`/auth/me`, favoritos, admin) | Passo 10 (roles `datastore.user`/`secretmanager.secretAccessor`) não foi feito | Conceder as duas roles à `backend-run@{projeto}` |
| Login falha na troca do código OAuth | Redirect URI cadastrado no Google Console não bate com a URL real do frontend, ou o secret errado (`_DEV` num projeto, `_PROD` no outro) | Conferir passo 11 (as 2 URLs por ambiente) e que cada projeto lê o par de secrets com o sufixo certo |
| `/admin` não abre para ninguém | `scripts/seed_admin.py` (passo 14) não foi rodado nesse projeto | Rodar o script apontando pro `project_id` certo |
| Login funciona em dev mas nunca em prod (ou vice-versa), sem erro claro | `project_id` de prod não termina em `-prod` (ou o de dev não termina em `-dev`) — `core/secrets.py::_is_prod()` sempre resolveu pro par de secrets errado | Ver o aviso obrigatório do passo 3 — não tem correção sem renomear o projeto ou (não recomendado) editar `_is_prod()` |
| Deploy de app em prod nunca termina, fica "Waiting" indefinidamente no Actions | Gate de aprovação do passo 8.1 configurado, mas ninguém aprovou ainda | Abrir o run → Review deployments → Approve and deploy (é o comportamento esperado, não é erro) |
| Deploy de app em prod roda sozinho, sem pedir aprovação, mesmo tendo criado o environment "production" | Nome do environment não é exatamente `production`, ou "Required reviewers" não foi marcado nas Settings | Revisar passo 8.1 — o nome precisa bater com `environment: production` do YAML |

---

## Referências

- `CLAUDE.md` — convenções gerais, estrutura de pastas, CI/CD
- [ADR-0002 — GCP como cloud provider](../adr/ADR-0002-gcp-como-cloud-provider.md)
- [ADR-0003 — Terraform por diretório de ambiente](../adr/ADR-0003-terraform-diretorios-por-ambiente.md)
- [ADR-0004 — Workload Identity Federation](../adr/ADR-0004-workload-identity-federation.md)
- [ADR-009 — ACL de usuário × projeto](../adr/ADR-009-acl-usuario-projeto.md)
- [`infra/terraform/bootstrap/README.md`](../../infra/terraform/bootstrap/README.md)
- [`docs/specs/admin.md`](../specs/admin.md) — bootstrap do primeiro admin, casos de borda do ACL
- `CHANGELOG.md`, seção "Fase 1" — incidentes reais do bootstrap original
