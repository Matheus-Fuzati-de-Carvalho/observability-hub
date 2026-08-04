# observability-hub

Plataforma de observabilidade de dados no GCP. Monorepo com backend, frontend e infraestrutura versionados juntos, com dois ambientes (`dev` e `prod`) espelhados por Terraform.

Este documento é a fonte de verdade das convenções do projeto. Qualquer sessão (humana ou do Claude Code) deve seguir o que está aqui. Se uma convenção mudar, atualize este arquivo no mesmo PR.

## Visão geral do domínio

O produto monitora datasets e tabelas do BigQuery em toda a organização e expõe:

| Funcionalidade | O que faz | Fonte de dados principal |
|---|---|---|
| Catálogo | Inventário navegável de datasets/tabelas | `INFORMATION_SCHEMA` (BigQuery) |
| Lineage e tabelas órfãs | Reconstrói relações de dependência entre tabelas e identifica tabelas sem consumidores conhecidos | Cloud Logging (audit logs de jobs BigQuery) |
| Fingerprinting de PII | Detecta colunas com dados pessoais sensíveis | `INFORMATION_SCHEMA` + amostragem de dados |
| Mapa de acesso | Quem acessou o quê e quando | Cloud Logging (data access audit logs) |
| Qualidade de dados e schema drift | Detecta mudanças de schema e quebras de contrato | `INFORMATION_SCHEMA` (snapshots ao longo do tempo) |
| Freshness com SLA | Monitora se tabelas estão sendo atualizadas dentro do esperado | Metadados de última modificação (BigQuery) |
| FinOps | Scanner de desperdício (tabelas não usadas, partições mal configuradas) e acompanhamento de budget | BigQuery + Cloud Billing |

Esses sete domínios são a espinha dorsal da estrutura de pastas do backend e do frontend — cada um vira um módulo isolado, não uma feature espalhada por camadas transversais.

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
│   │   │   │   └── finops/
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
├── scripts/                      # Scripts de apoio (setup local, seed, etc.)
├── CLAUDE.md
└── .gitignore
```

Regra geral: **domains/ (backend) e features/ (frontend) espelham exatamente os 7 domínios da tabela acima**. Ao adicionar uma funcionalidade nova, ela ganha uma pasta própria nos dois lados — não se mistura lógica de domínios diferentes no mesmo módulo.

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
- **Merge/push em `main`** → build + deploy automático no ambiente **prod** (`observability-hub-prod`).

Diretrizes para os workflows quando forem criados:

- Autenticação no GCP exclusivamente via Workload Identity Federation — nenhuma service account key em segredo do GitHub.
- Workflows separados por app e por ambiente (ex: `backend-deploy-dev.yml`, `backend-deploy-prod.yml`, `frontend-deploy-dev.yml`, `frontend-deploy-prod.yml`, `terraform-plan.yml`, `terraform-apply-dev.yml`, `terraform-apply-prod.yml`), todos vivendo em `.github/workflows/`.
- `terraform plan` roda em todo PR que toca `infra/terraform/**`; `apply` só roda após merge, no ambiente correspondente.
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
- Nesta fase (Fase 0), o repositório contém apenas estrutura e documentação — nenhum código de aplicação, pipeline ou Terraform real ainda existe além do que este arquivo descreve como convenção futura.
