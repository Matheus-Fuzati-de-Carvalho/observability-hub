# Bootstrap

Cria, por ambiente, a fundação que o resto do Terraform (`infra/terraform/environments/`) e o GitHub Actions precisam para existir:

- Bucket GCS de remote state (`<project_id>-tfstate`)
- APIs do GCP necessárias habilitadas no projeto
- Workload Identity Pool + Provider OIDC confiando no GitHub Actions
- Service account de deploy, restrita ao repositório `Matheus-Fuzati-de-Carvalho/observability-hub`
  - `dev`: qualquer branch pode assumir a identidade
  - `prod`: só a branch `main` pode assumir a identidade

Aplicado **manualmente, fora do CI**, uma vez por ambiente — é o único ponto do projeto com state local (não há ainda um bucket remoto para guardar o próprio state do bootstrap).

## Pré-requisitos

- `gcloud auth application-default login` feito com uma conta que tenha permissão de Owner (ou papéis equivalentes: Project IAM Admin, Service Usage Admin, Storage Admin, Workload Identity Pool Admin, Service Account Admin) nos dois projetos.
- Faturamento habilitado em `observability-hub-dev` e `observability-hub-prod`.

## Aplicar

```bash
# dev
cd infra/terraform/bootstrap/dev
terraform init
terraform plan
terraform apply

# prod
cd ../prod
terraform init
terraform plan
terraform apply
```

## Depois de aplicar

Cada diretório expõe três outputs que serão usados nas próximas fases:

```bash
terraform output state_bucket_name
terraform output workload_identity_provider
terraform output service_account_email
```

- `state_bucket_name` → vai no bloco `backend "gcs"` de `infra/terraform/environments/<env>`.
- `workload_identity_provider` e `service_account_email` → vão nos inputs `workload_identity_provider` e `service_account` da action `google-github-actions/auth` nos workflows de `.github/workflows/` (Fase seguinte).

## Importante

- `terraform.tfstate` local destes diretórios **não é versionado** (está no `.gitignore` do repo) e é a única cópia do state do bootstrap. Faça um backup dele fora do Git (ex: gerenciador de segredos, bucket privado separado) — sem ele, o Terraform perde o rastro dos recursos já criados e uma reaplicação pode tentar recriar algo que já existe.
- `.terraform.lock.hcl` **é** versionado (mesmo espírito do `uv.lock`/`pnpm-lock.yaml`): trava a versão do provider `google` para reprodutibilidade.
- O bucket de state tem `prevent_destroy = true`: `terraform destroy` neste módulo não vai apagá-lo por engano.
- Os papéis concedidos ao service account de deploy (`locals.deployer_roles` em `modules/wif-bootstrap/main.tf`) cobrem os módulos já planejados (`cloud-run`, `artifact-registry`, `bigquery`, `secret-manager`, `logging-sink`). Revisite essa lista à medida que esses módulos forem escritos — em especial `roles/iam.serviceAccountUser`, hoje concedido a nível de projeto porque a service account de runtime do Cloud Run ainda não existe; assim que existir, vale restringir esse papel só a ela.
