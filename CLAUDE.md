# observability-hub

Plataforma de observabilidade de dados no GCP. Monorepo com backend, frontend e infraestrutura versionados juntos, com dois ambientes (`dev` e `prod`) espelhados por Terraform.

Este documento é a fonte de verdade das convenções do projeto. Qualquer sessão (humana ou do Claude Code) deve seguir o que está aqui. Se uma convenção mudar, atualize este arquivo no mesmo PR.

## Visão geral do domínio

O produto monitora BigQuery (todos os datasets/tabelas da organização) e, a partir da expansão iniciada em 2026-08-18, também Cloud Storage — primeiro passo de uma frente maior de cobertura pra além do BigQuery (Storage → Scheduler → Workflows, nessa ordem de prioridade, ver `docs/specs/storage.md` seção 1):

| Funcionalidade | O que faz | Fonte de dados principal |
|---|---|---|
| Catálogo | Inventário navegável de datasets/tabelas | `INFORMATION_SCHEMA` (BigQuery) |
| Lineage e tabelas órfãs | Reconstrói relações de dependência entre tabelas (incluindo bucket do GCS como nó, via jobs LOAD/EXTRACT) e identifica tabelas sem consumidores conhecidos | Cloud Logging (audit logs de jobs BigQuery) |
| Fingerprinting de PII | Detecta colunas com dados pessoais sensíveis | `INFORMATION_SCHEMA` + amostragem de dados |
| Mapa de acesso | Quem acessou o quê e quando | Cloud Logging (data access audit logs) |
| Qualidade de dados e schema drift | Detecta mudanças de schema e quebras de contrato | `INFORMATION_SCHEMA` (snapshots ao longo do tempo) |
| Freshness com SLA | Monitora se tabelas estão sendo atualizadas dentro do esperado | Metadados de última modificação (BigQuery) |
| FinOps | Scanner de desperdício (tabelas não usadas, partições mal configuradas) e acompanhamento de budget | BigQuery + Cloud Billing |
| Cloud Storage | Catálogo de buckets, scanner de desperdício (idade + config, com confirmação opcional de uso real via audit log) | Cloud Storage API + Cloud Logging (audit logs de leitura de objeto) |

Esses oito domínios são a espinha dorsal da estrutura de pastas do backend e do frontend — cada um vira um módulo isolado, não uma feature espalhada por camadas transversais. `storage` é o único que não segue o agrupamento "BigQuery" da sidebar (`SidebarServiceGroup` próprio, "Cloud Storage") — ver `docs/specs/storage.md`.

## Stack

- **Backend**: Python + FastAPI, gerenciado com `uv`
- **Frontend**: React + Vite + TypeScript + shadcn/ui + Tailwind, gerenciado com `pnpm`
- **Container**: Docker (build multi-stage)
- **IaC**: Terraform, diretórios por ambiente (`environments/dev`, `environments/prod`) — **não** usar Terraform workspaces
- **CI/CD**: GitHub Actions + Workload Identity Federation (sem chaves de service account)

## Projetos e ambientes GCP

| Ambiente | Projeto GCP | Branch/gatilho |
|---|---|---|
| dev | `observability-hub-dev` | qualquer push em qualquer branch (exceto `main`) |
| prod | `observability-hub-prod` | merge/push em `main` |

Nunca compartilhar recursos entre `dev` e `prod`. Cada ambiente tem seu próprio state do Terraform, service accounts, secrets e imagens no Artifact Registry.

## Serviços GCP e seu papel

- **Cloud Run**: hospeda backend (FastAPI) e frontend (build estático servido via container)
- **BigQuery**: fonte de metadados via `INFORMATION_SCHEMA`; alvo de análise de todos os domínios
- **Cloud Logging**: audit logs usados para lineage e mapa de acesso
- **Artifact Registry**: imagens Docker do backend e frontend
- **Secret Manager**: credenciais e segredos em runtime (nunca em variáveis de ambiente estáticas ou baked na imagem)
- **GCS**: remote state do Terraform (bucket criado uma vez em `infra/terraform/bootstrap`, um prefixo por ambiente)

## Estrutura de pastas

```
.
├── .github/workflows/          # Pipelines de CI/CD (Fase 1)
├── apps/
│   ├── backend/
│   │   ├── src/observability_hub/
│   │   │   ├── api/            # Routers FastAPI, schemas de request/response (camada HTTP)
│   │   │   ├── domains/        # Lógica de negócio, um subpacote por funcionalidade
│   │   │   │   ├── catalog/
│   │   │   │   ├── lineage/
│   │   │   │   ├── pii/
│   │   │   │   ├── access/
│   │   │   │   ├── quality/
│   │   │   │   ├── freshness/
│   │   │   │   ├── finops/
│   │   │   │   ├── auth/        # Domínio de plataforma (não é dos 7 de observabilidade) — login OAuth, sessão
│   │   │   │   └── admin/       # Domínio de plataforma — ACL de usuário×projeto, ver docs/specs/admin.md
│   │   │   └── core/            # Config, clients GCP compartilhados, logging, exceptions, auth
│   │   └── tests/
│   │       ├── unit/            # Espelha domains/, sem chamadas reais ao GCP
│   │       └── integration/     # Testes contra emuladores/projeto dev
│   └── frontend/
│       ├── src/
│       │   ├── app/             # Setup de rotas, providers, layout raiz
│       │   ├── features/        # Um subpacote por funcionalidade (mesmos 7 domínios)
│       │   ├── components/ui/   # Primitivas shadcn/ui (geradas via CLI, não escritas à mão)
│       │   ├── hooks/           # Hooks compartilhados entre features
│       │   ├── lib/             # Cliente HTTP, utils
│       │   └── types/           # Tipos compartilhados (ex: gerados a partir do OpenAPI do backend)
│       └── public/
├── infra/terraform/
│   ├── bootstrap/                # Recursos fundacionais: bucket de state, pool WIF (apply manual, uma vez)
│   ├── modules/                  # Módulos reutilizáveis (cloud-run, bigquery, artifact-registry, secret-manager, logging-sink)
│   └── environments/
│       ├── dev/                  # Root module do ambiente dev, consome modules/
│       └── prod/                 # Root module do ambiente prod, consome modules/
├── docs/adr/                     # Architecture Decision Records
├── docs/playbooks/                # Roteiros operacionais de execução rápida (ex: liberar
│                                   # um projeto GCP pro Hub, hospedar o Hub em projetos novos)
├── scripts/                      # Scripts de apoio (setup local, seed, etc.)
├── CLAUDE.md
└── .gitignore
```

Regra geral: **domains/ (backend) e features/ (frontend) espelham exatamente os domínios da tabela acima**. Ao adicionar uma funcionalidade nova, ela ganha uma pasta própria nos dois lados — não se mistura lógica de domínios diferentes no mesmo módulo.

## Convenções — Backend

- Python 3.12, dependências e ambiente virtual via `uv` (`uv.lock` é commitado).
- Lint e formatação: `ruff` (lint + format em uma ferramenta só, sem Black/isort/flake8 separados).
- Validação e config: Pydantic v2 + `pydantic-settings`. Nunca ler `os.environ` diretamente fora de `core/config.py`.
- Endpoints FastAPI ficam em `api/`; lógica de negócio nunca vive no router — o router chama uma função/classe de `domains/`.
- Clients de GCP (BigQuery, Logging, Secret Manager) são inicializados uma vez em `core/` e injetados via `Depends`, nunca instanciados dentro de um domínio.
- As libs oficiais do GCP (`google-cloud-*`) são majoritariamente síncronas. Endpoints que as chamam devem ser `def` (não `async def`) para que o FastAPI rode em threadpool, ou usar `run_in_threadpool` explicitamente — nunca bloquear o event loop.
- Logs estruturados em JSON (compatível com Cloud Logging), nunca `print()`.
- Testes com `pytest`. `tests/unit` não toca GCP (mocka os clients); `tests/integration` roda contra o projeto `dev`.

## Convenções — Frontend

- TypeScript estrito (`strict: true`), sem `any` implícito.
- Componentes de UI vêm do `shadcn/ui` — adicionar via CLI (`npx shadcn add ...`), não copiar/colar manualmente.
- Lint e formatação: `biome` (substitui ESLint + Prettier, uma config só, coerente com a filosofia de baixa manutenção da stack).
- Data fetching: TanStack Query — nenhuma chamada `fetch` direta dentro de componentes de página.
- Roteamento: React Router.
- Estado: preferir estado de servidor via TanStack Query + estado local de componente. Só introduzir uma lib de estado global (ex: Zustand) se houver necessidade concreta — não antecipar.
- Node 22 LTS, gerenciador de pacotes `pnpm` (lockfile `pnpm-lock.yaml` é commitado).
- Testes com Vitest + React Testing Library.

## Convenções — Docker

- Build multi-stage (stage de build separado do stage final de runtime).
- Imagem final roda como usuário não-root.
- Um `Dockerfile` por app (`apps/backend/Dockerfile`, `apps/frontend/Dockerfile`).
- Tag de imagem no Artifact Registry: `<region>-docker.pkg.dev/<gcp-project>/<repo>/<app>:<git-sha>`. Nunca usar `:latest` em deploy.

## Convenções — Terraform

- Diretórios por ambiente (`environments/dev`, `environments/prod`), **não** workspaces — cada ambiente é uma raiz de execução independente.
- Módulos reutilizáveis em `modules/`; cada ambiente só declara `module "..." { source = "../../modules/..." }` + variáveis específicas do ambiente + backend.
- `infra/terraform/bootstrap` é aplicado manualmente (fora do CI), uma única vez por ambiente, para criar o bucket GCS de state e o pool/provider de Workload Identity Federation — ele não pode depender de um backend remoto que ainda não existe.
- Backend do state: GCS, um bucket (ou um prefixo por ambiente dentro do mesmo bucket) definido em `bootstrap`.
- Nenhum valor sensível em `.tfvars` commitado — usar `*.tfvars.example` como referência e injetar valores reais via CI ou `.tfvars` local (gitignored).
- Nomenclatura de recursos: prefixar com o nome do projeto e ambiente quando o recurso não isolar por projeto GCP sozinho (ex: `observability-hub-dev-<recurso>`).

## CI/CD e deploy

Gatilhos (a implementar em `.github/workflows/` na Fase 1, mas já são a política oficial de deploy):

- **Push em qualquer branch** (exceto `main`) → build + deploy automático no ambiente **dev** (`observability-hub-dev`).
- **Merge/push em `main`** → build + deploy **de app** (`backend-deploy-prod.yml`, `frontend-deploy-prod.yml`) só roda depois de aprovação manual — os dois jobs usam `environment: production` (GitHub Environment com "required reviewers" configurado nas Settings do repo), então ficam em "Waiting" até alguém aprovar. `terraform-apply-prod.yml` continua automático (decisão consciente, 2026-08-18 — mudança de infra já passa por `terraform plan` revisado antes do merge; só o deploy de app, que sobe uma imagem nova sem revisão nenhuma no meio, ganhou o gate).

Diretrizes para os workflows quando forem criados:

- Autenticação no GCP exclusivamente via Workload Identity Federation — nenhuma service account key em segredo do GitHub.
- Workflows separados por app e por ambiente (ex: `backend-deploy-dev.yml`, `backend-deploy-prod.yml`, `frontend-deploy-dev.yml`, `frontend-deploy-prod.yml`, `terraform-plan.yml`, `terraform-apply-dev.yml`, `terraform-apply-prod.yml`), todos vivendo em `.github/workflows/`.
- `terraform plan` roda em todo PR que toca `infra/terraform/**` — mas só para **dev**. O WIF de prod (`infra/terraform/bootstrap/prod`) tem `attribute_condition` restrito a `assertion.ref == "refs/heads/main"`, então nunca autentica em `pull_request` (roda em `refs/pull/N/merge`); revisar `terraform plan` de prod localmente antes de merges que tocam infra é responsabilidade manual até essa restrição ser revisitada. `apply` só roda após merge, no ambiente correspondente.
- Deploy em prod não deve exigir Terraform workspace switch nem lógica condicional complexa — o ambiente é determinado pelo diretório (`environments/dev` vs `environments/prod`), não por uma flag em runtime.
- Imagem Docker é buildada uma vez e promovida (mesma tag/digest) de dev para prod quando possível, evitando rebuild entre ambientes — a validar na Fase 1 conforme a estratégia de branch adotada.

## Git e Claude Code

- Claude Code está autorizado a rodar `git add` e `git commit` automaticamente ao longo do desenvolvimento.
- **Sempre pedir aprovação explícita do usuário antes de qualquer `git push`** — commits locais não pedem aprovação, pushes sim.
- Commits seguem [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`).
- Branches: `feature/<descrição>`, `fix/<descrição>`, `chore/<descrição>`. Lembre-se: qualquer push nessas branches dispara deploy em dev — evitar pushes intermediários "quebrados" quando possível.

## Guardrails

- Nunca commitar segredos, chaves de service account ou arquivos `.env` reais (ver `.gitignore`).
- Nunca misturar recursos/dados de `dev` e `prod`.
- Nunca usar Terraform workspaces — a separação de ambiente é sempre por diretório.
- Nunca colocar lógica de negócio em `api/` (backend) ou chamadas HTTP direto em componentes de página (frontend).
- Fase 0 (estrutura e documentação) e Fase 1 (bootstrap do Terraform, módulo `infra/terraform/modules/cloud-run/`, root modules de `environments/{dev,prod}`, workflows em `.github/workflows/` e backend skeleton com `GET /health` em `apps/backend/`) concluídas — dev e prod com Cloud Run, Artifact Registry e CI/CD funcionando de ponta a ponta. Ainda não existem: os demais módulos de `infra/terraform/modules/` (artifact-registry standalone já é interno ao módulo cloud-run; faltam bigquery, secret-manager, logging-sink), lógica de domínio em `apps/backend/src/observability_hub/domains/`, e nenhum código em `apps/frontend/`.

## Registro de acessos e configurações

O produto existe pra ser apontado a projetos GCP de clientes (ver
[ADR-006](docs/adr/ADR-006-cross-project.md), modelo de acesso
cross-project). `docs/onboarding-cliente.md` é o checklist vivo de tudo
que um projeto alvo precisa ter (APIs habilitadas, roles IAM concedidas à
service account de runtime do Hub, audit logs configurados) para aceitar
leitura do Hub — vira a base do documento de implementação entregue a um
cliente real no futuro.

**Toda vez que uma sessão liberar, alterar ou descobrir algum dos itens
abaixo — em qualquer projeto GCP, incluindo os próprios
`observability-hub-dev`/`observability-hub-prod` servindo de projeto-alvo
um do outro —, isso entra na tabela "Registro de acessos concedidos" de
`docs/onboarding-cliente.md` antes de considerar a tarefa concluída:**
- `gcloud services enable` de qualquer API num projeto alvo
- `gcloud projects add-iam-policy-binding` (ou remoção) de qualquer role
  pra uma service account do Hub
- Mudança em `auditConfigs` (Data Access audit logs) de um projeto
- Qualquer nova role passando a ser lida pelo código (ex: um domínio novo
  que passa a exigir uma permissão que nenhum outro pedia)

Isso vale tanto para mudanças aplicadas via Terraform quanto para comandos
`gcloud` rodados manualmente pelo usuário (via `!`) — não assumir que o
comando fornecido foi executado; confirmar com `gcloud ... get-iam-policy`
(ou equivalente) antes de marcar a linha como concedida. Se o checklist de
roles necessárias mudar (ex: um domínio novo passa a precisar de uma role
que a lista atual não cobre), atualizar também a tabela de roles do
próprio `docs/onboarding-cliente.md`, não só o log de concessões.

## Contextos de trabalho

Dependendo do escopo da tarefa, assuma o contexto correspondente abaixo.
Cada contexto define foco, prioridades e checklist antes de considerar uma tarefa concluída.

---

### Contexto: IaC (infra/terraform/)

**Foco:** segurança, idempotência, custo e rastreabilidade.

Antes de criar ou editar qualquer .tf:
- Verificar se existe módulo reutilizável em modules/ antes de duplicar código
- Nunca hardcodar project_id, region ou valores de ambiente — sempre variáveis
- Sempre rodar terraform fmt + terraform validate antes de commitar
- Rodar terraform plan e apresentar o output para aprovação antes de apply
- Confirmar que deletion_protection = true em recursos de prod
- Labels obrigatórias em todos os recursos: environment, managed-by = terraform

Checklist de entrega:
- [ ] terraform validate passou
- [ ] terraform plan revisado e aprovado
- [ ] Nenhum secret ou credencial em .tf ou .tfvars commitados
- [ ] README.md do módulo atualizado se necessário
- [ ] Se o recurso concede acesso a um projeto alvo (IAM binding
      cross-project, API habilitada, audit config) — registrado em
      `docs/onboarding-cliente.md`, ver "Registro de acessos e configurações"

---

### Contexto: Backend (apps/backend/)

**Foco:** corretude do domínio, testabilidade e custo de queries BQ.

Antes de implementar qualquer domínio:
- Ler a spec em docs/specs/<domínio>.md — não implementar sem spec aprovada
- Lógica de negócio fica em domains/, nunca em api/
- Clients GCP inicializados em core/, injetados via Depends
- Endpoints que chamam libs GCP síncronas devem ser def, não async def
- Toda query BigQuery deve ter estimativa de custo (dry run) antes de implementar
- Logs estruturados em JSON, nunca print()

Checklist de entrega:
- [ ] Spec do domínio existe e foi seguida
- [ ] Testes unitários em tests/unit/ cobrindo lógica principal
- [ ] pytest passou sem erros
- [ ] Nenhuma chamada GCP em tests/unit/ (usar mocks)
- [ ] ruff check e ruff format sem erros

---

### Contexto: Frontend (apps/frontend/)

**Foco:** fidelidade à identidade visual dp6, densidade de informação estilo Metabase, UX funcional.

Antes de criar qualquer componente:
- Ler docs/skills/frontend.md obrigatoriamente
- Usar apenas as cores, fontes e padrões definidos na skill
- Componentes de UI via shadcn/ui — nunca escrever CSS do zero para primitivas
- Data fetching exclusivamente via TanStack Query — nunca fetch direto em componentes
- TypeScript strict — sem any

Checklist de entrega:
- [ ] Skill de frontend foi lida
- [ ] Cores e fontes seguem a identidade dp6
- [ ] pnpm lint (biome) e pnpm build sem erros

---

### Contexto: CI/CD (.github/workflows/)

**Foco:** segurança de secrets, ordem de execução e falha rápida.

Regras obrigatórias:
- Autenticação GCP exclusivamente via WIF — nunca service account keys
- Workflows de deploy de app sempre com needs: apontando para o terraform apply correspondente quando o push tocar infra/ e apps/ juntos
- Secrets referenciados sempre como ${{ secrets.NOME }} — nunca valores literais
- Todo workflow deve ter permissions: explícito (principle of least privilege)
- Usar actions fixadas em SHA ou tag de versão (ex: actions/checkout@v4)

Checklist de entrega:
- [ ] Nenhum secret literal no YAML
- [ ] permissions: definido explicitamente
- [ ] Ordem de jobs garantida com needs: onde necessário
- [ ] Testado com um push real ou via act localmente

---

### Contexto: Spec e documentação (docs/)

**Foco:** clareza, completude e rastreabilidade de decisões.

Ao criar uma spec de domínio (docs/specs/<domínio>.md), incluir obrigatoriamente:
- Objetivo e problema que resolve
- Fonte de dados (qual API/tabela BQ/log)
- Endpoints da API (método, path, parâmetros, response schema)
- Queries BigQuery planejadas com estimativa de custo
- Casos de borda e comportamento esperado
- O que está fora do escopo desta spec

Ao atualizar o CHANGELOG.md:
- Registrar o que foi feito, erros cometidos e aprendizados
- Registrar qualquer mudança de arquitetura com justificativa
- Atualizar o status das fases na tabela de próximas fases

Ao criar um ADR:
- Seguir o padrão: contexto → decisão → alternativas consideradas → consequências
- Nunca apagar um ADR — se a decisão mudar, criar um novo ADR referenciando o anterior

---

## Gestão de contexto de sessão

### Quando atualizar o SESSIONLOG.md
- Quando /status mostrar uso acima de 60% do contexto
- Ao final de cada fase concluída
- Antes de qualquer reset ou /compact de sessão
- Quando o usuário pedir explicitamente

### O que o SESSIONLOG.md deve conter
- Status atual (fase, próximo passo exato)
- Lista de commits desta sessão
- Decisões importantes tomadas e por quê
- Erros encontrados e como foram resolvidos
- Estado atual da infraestrutura (GCP, GitHub Secrets, etc.)
- Como retomar após reset

### Ao iniciar uma nova sessão
1. Ler CLAUDE.md obrigatoriamente (sempre)
2. Verificar se existe SESSIONLOG.md — se sim, ler antes de qualquer ação
3. Confirmar com o usuário o próximo passo antes de executar
4. Nunca assumir o estado do projeto sem ler os dois arquivos

### Comandos úteis de contexto
- `/status` — ver uso atual de contexto e limites da sessão
- `/compact` — comprimir histórico preservando contexto essencial
- `/clear` — resetar sessão completamente (usar SESSIONLOG.md para retomar)
