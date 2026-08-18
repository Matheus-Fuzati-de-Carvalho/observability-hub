# Observability Hub — Manual de Implementação

**Hospedagem em ambiente Google Cloud próprio**

---

## Sobre este manual

Este documento orienta a implementação de uma instância própria do
Observability Hub no seu ambiente Google Cloud — hospedagem e
administração completas sob seu controle.

**Quem deve executar:** um responsável técnico com papel de
*Owner* (ou equivalente) no Google Cloud e acesso ao repositório de
código da aplicação.

**Tempo estimado:** meio dia de trabalho técnico, considerando a
validação de cada etapa antes de avançar para a próxima.

---

## Segurança e escopo — o que este processo faz (e o que não faz)

- **Tudo acontece dentro dos seus próprios projetos Google Cloud**, sob
  seu faturamento e sob seu controle total. Nenhum recurso é criado fora
  do que está descrito neste manual.
- **Nenhuma credencial de longa duração é criada ou armazenada.** A
  autenticação entre o GitHub e o Google Cloud usa *Workload Identity
  Federation* — o GitHub troca um token temporário por uma credencial do
  Google válida por poucos minutos, a cada execução. Não existe "senha"
  ou chave salva em segredo nenhum.
- **Permissões mínimas necessárias**, sempre restritas aos dois projetos
  que você mesmo cria neste processo — nunca a nenhum outro recurso da
  sua organização.
- **Processo reversível.** Apagar os dois projetos ao final remove tudo
  o que foi criado, sem deixar rastro em nenhum outro sistema.
- **Nenhum dado seu trafega para fora do seu ambiente Google Cloud** como
  parte deste processo — a hospedagem é inteiramente sua.
- **Auditável de ponta a ponta.** A infraestrutura é definida como código
  (Terraform) — cada recurso que será criado pode ser revisado antes de
  ser aplicado, e cada comando deste manual é explicado antes de ser
  executado.

---

## Visão geral

Ao final deste processo, você terá dois ambientes independentes (teste e
produção), cada um com:

- Duas aplicações web rodando em Cloud Run — o backend (API) e o
  frontend (interface)
- Um banco de dados (Firestore) para preferências e controle de acesso
  interno da aplicação
- Um cofre de credenciais (Secret Manager) para as chaves de login
- Autenticação do GitHub para o Google Cloud sem nenhuma chave estática

```
Repositório de código  →  Pipeline de implantação  →  Aplicação no ar
      (GitHub)               (sem credenciais fixas)      (Cloud Run)
```

O ambiente de **teste** recebe atualizações a cada alteração de código;
o ambiente de **produção**, só quando uma alteração é formalmente
aprovada e publicada.

---

## Antes de começar

- Acesso ao Google Cloud com papel de *Owner* (ou os papéis
  equivalentes: Administrador de IAM do Projeto, Administrador de Uso de
  Serviços, Administrador de Storage, Administrador de Workload Identity
  Pool, Administrador de Service Account).
- Uma conta de faturamento (billing) do Google Cloud disponível para
  vincular aos dois projetos novos.
- O Terraform instalado (versão 1.7 ou superior).
- Uma cópia do repositório de código da aplicação sob seu próprio
  controle (fork ou cópia direta), já que alguns arquivos de
  configuração precisam ser ajustados com os nomes dos seus projetos.
- Acesso para configurar segredos no repositório do GitHub.

---

## Etapa 1 — Criar os dois projetos Google Cloud

> ⚠️ **Antes de escolher os nomes**: o identificador do projeto de teste
> precisa terminar em `-dev` e o de produção precisa terminar em
> `-prod` (ex: `suaempresa-dev` / `suaempresa-prod`). Isso não é só uma
> sugestão de organização — a aplicação usa essa terminação para saber
> automaticamente qual conjunto de credenciais de login usar em cada
> ambiente. Um nome fora desse padrão faz o login falhar de forma
> silenciosa no ambiente de produção.

```bash
gcloud projects create {PROJETO_TESTE} --name="Observability Hub (teste)"
gcloud projects create {PROJETO_PRODUCAO} --name="Observability Hub (produção)"

gcloud billing projects link {PROJETO_TESTE} --billing-account={ID_DA_CONTA_DE_FATURAMENTO}
gcloud billing projects link {PROJETO_PRODUCAO} --billing-account={ID_DA_CONTA_DE_FATURAMENTO}
```

O ID da conta de faturamento pode ser consultado com
`gcloud billing accounts list`.

---

## Etapa 2 — Provisionar o banco de dados da aplicação

A aplicação guarda preferências de usuário e o controle de acesso
interno em um banco Firestore. Esta etapa cria esse banco, uma vez por
projeto, antes de qualquer outra coisa:

```bash
gcloud services enable firestore.googleapis.com --project={PROJETO}

gcloud firestore databases create \
  --project={PROJETO} \
  --location={REGIAO} \
  --type=firestore-native
```

Repita para os dois projetos.

---

## Etapa 3 — Ajustar a configuração para os seus projetos

O repositório de código faz referência aos nomes dos projetos originais
em alguns arquivos de configuração. Antes de aplicar qualquer coisa,
substitua esses nomes pelos escolhidos na Etapa 1 nos seguintes
arquivos:

| Arquivo | O que ajustar |
|---|---|
| `infra/terraform/bootstrap/dev/variables.tf` | Nome do projeto de teste e repositório GitHub |
| `infra/terraform/bootstrap/prod/variables.tf` | Nome do projeto de produção e repositório GitHub |
| `infra/terraform/environments/dev/variables.tf` | Nome do projeto de teste |
| `infra/terraform/environments/prod/variables.tf` | Nome do projeto de produção |
| `infra/terraform/environments/dev/versions.tf` | Nome do bucket de estado do Terraform (teste) |
| `infra/terraform/environments/prod/versions.tf` | Nome do bucket de estado do Terraform (produção) |
| Os 4 arquivos de pipeline em `.github/workflows/` (`backend-deploy-*`, `frontend-deploy-*`) | Nome do projeto correspondente |

---

## Etapa 4 — Preparar a base de implantação (uma vez por ambiente)

Esta etapa cria a fundação necessária: o local de armazenamento seguro
do estado da infraestrutura, a confiança entre GitHub e Google Cloud, e
a identidade usada nas implantações automáticas.

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

`terraform plan` mostra exatamente o que será criado antes de qualquer
mudança real — revise antes de confirmar com `terraform apply`.

Ao final, capture os três resultados de cada ambiente (serão usados na
próxima etapa):

```bash
terraform output state_bucket_name
terraform output workload_identity_provider
terraform output service_account_email
```

---

## Etapa 5 — Conectar o GitHub ao Google Cloud

No repositório GitHub, em Configurações → Secrets and variables →
Actions, cadastre quatro segredos com os valores obtidos na etapa
anterior:

```bash
gh secret set WIF_PROVIDER_DEV --body "<valor de workload_identity_provider, teste>"
gh secret set WIF_SA_DEV --body "<valor de service_account_email, teste>"
gh secret set WIF_PROVIDER_PROD --body "<valor de workload_identity_provider, produção>"
gh secret set WIF_SA_PROD --body "<valor de service_account_email, produção>"
```

Isso é o que permite que o pipeline de implantação autentique no Google
Cloud sem nenhuma chave fixa, como descrito na seção de segurança acima.

### Aprovação obrigatória antes de qualquer atualização em produção

O ambiente de produção **não** publica uma atualização sozinho — mesmo
depois de o código estar pronto, alguém precisa aprovar manualmente
antes de ela realmente subir. Configure isso agora, também em
Configurações → Environments:

1. **New environment**, nome exatamente `production`
2. Marque **"Required reviewers"** e adicione quem deve aprovar
   atualizações de produção
3. Salve

Sem este passo, o ambiente de produção volta a publicar automaticamente
a cada alteração — a aprovação manual só existe se este environment
estiver configurado.

---

## Etapa 6 — Primeira implantação da infraestrutura

Com os arquivos da Etapa 3 já salvos no repositório, publique-os em uma
branch de trabalho (não a branch principal) — isso cria automaticamente
as duas aplicações (backend e frontend) no ambiente de teste, com uma
imagem inicial temporária.

Confirme que a execução foi concluída com sucesso antes de prosseguir.

Para o ambiente de produção, essa mesma criação só acontece quando as
alterações forem publicadas na branch principal — deixe para depois de
validar tudo em teste (Etapa 11).

---

## Etapa 7 — Conceder as permissões internas da aplicação

A aplicação backend precisa de duas permissões para funcionar — acesso
ao banco de dados (Etapa 2) e ao cofre de credenciais (próxima etapa).
Conceda em cada um dos dois projetos:

```bash
CONTA_DE_SERVICO="backend-run@{PROJETO}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding {PROJETO} \
  --member="serviceAccount:${CONTA_DE_SERVICO}" --role="roles/datastore.user"

gcloud projects add-iam-policy-binding {PROJETO} \
  --member="serviceAccount:${CONTA_DE_SERVICO}" --role="roles/secretmanager.secretAccessor"
```

Essas permissões existem só dentro do próprio projeto — não concedem
acesso a nada externo.

---

## Etapa 8 — Configurar o login (Google OAuth)

A aplicação usa "Entrar com Google" para autenticação, solicitando
apenas identificação básica (nome, e-mail, foto de perfil) — nenhuma
permissão sensível.

1. No **Google Cloud Console → APIs & Services → OAuth consent screen**,
   configure a tela de consentimento (uso interno da organização, ou
   externo publicado em modo de produção, conforme sua preferência).
2. Em **APIs & Services → Credentials**, crie uma credencial do tipo
   "OAuth client ID" → "Web application" — uma para cada ambiente
   (teste e produção usam credenciais separadas).
3. Em **Authorized redirect URIs**, cadastre o endereço da aplicação
   frontend de cada ambiente seguido de `/auth/callback`. O endereço
   pode ser consultado com:
   ```bash
   gcloud run services describe frontend --project={PROJETO} --region={REGIAO} \
     --format='value(status.url)'
   ```
4. Anote o **Client ID** e o **Client Secret** de cada credencial — vão
   para o cofre de credenciais na próxima etapa.

---

## Etapa 9 — Guardar as credenciais de login

```bash
# ambiente de teste
echo -n "{CLIENT_ID_TESTE}"     | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID_DEV --data-file=- --project={PROJETO_TESTE}
echo -n "{CLIENT_SECRET_TESTE}" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET_DEV --data-file=- --project={PROJETO_TESTE}
echo -n "{CHAVE_ALEATORIA}"     | gcloud secrets create JWT_SECRET --data-file=- --project={PROJETO_TESTE}
echo -n '{"allowed_domains": ["seudominio.com"], "allowed_emails": []}' \
  | gcloud secrets create OAUTH_ALLOWLIST --data-file=- --project={PROJETO_TESTE}

# ambiente de produção
echo -n "{CLIENT_ID_PRODUCAO}"     | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID_PROD --data-file=- --project={PROJETO_PRODUCAO}
echo -n "{CLIENT_SECRET_PRODUCAO}" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET_PROD --data-file=- --project={PROJETO_PRODUCAO}
echo -n "{CHAVE_ALEATORIA_DIFERENTE}" | gcloud secrets create JWT_SECRET --data-file=- --project={PROJETO_PRODUCAO}
echo -n '{"allowed_domains": ["seudominio.com"], "allowed_emails": []}' \
  | gcloud secrets create OAUTH_ALLOWLIST --data-file=- --project={PROJETO_PRODUCAO}
```

`{CHAVE_ALEATORIA}` pode ser gerada com `openssl rand -hex 32` — use um
valor diferente em cada ambiente. `allowed_domains`/`allowed_emails`
definem quem pode entrar na aplicação — ajuste para a realidade da sua
equipe.

---

## Etapa 10 — Confirmar a implantação da aplicação

O pipeline de implantação constrói e publica as duas aplicações
automaticamente a cada alteração de código. Confirme que as execuções
mais recentes foram concluídas com sucesso antes de seguir para a
validação.

---

## Etapa 11 — Criar o primeiro administrador

Sem este passo, ninguém consegue acessar a área administrativa da
aplicação. Execute localmente, com suas próprias credenciais:

```bash
gcloud auth application-default login   # caso ainda não tenha feito

cd apps/backend
uv run python ../../scripts/seed_admin.py \
  --project {PROJETO_TESTE} --email {seu-email-administrador}
```

---

## Etapa 12 — Validar o ambiente de teste

1. Acesse o endereço da aplicação frontend de teste.
2. Clique em "Entrar com Google" e autentique com um e-mail autorizado
   na Etapa 9.
3. Se for o mesmo e-mail cadastrado como administrador (Etapa 11),
   confirme que a área administrativa está acessível.

Com isso, o ambiente de teste está validado e pronto para uso.

---

## Etapa 13 — Repetir para produção

1. Publique as alterações da Etapa 3 na branch principal do
   repositório — isso cria a infraestrutura de produção automaticamente.
2. **A publicação das duas aplicações fica parada esperando aprovação**
   (se a Etapa 5 foi configurada) — acesse a aba de execuções do
   repositório, localize a execução parada e aprove-a manualmente para
   que a atualização siga adiante.
3. Repita as Etapas 7 a 11 apontando para o projeto de produção.
4. Repita a validação da Etapa 12 no ambiente de produção.

---

## Verificação final

```
[ ] Nomes dos dois projetos escolhidos terminando em "-dev"/"-prod"
    (obrigatório, ver aviso na Etapa 1)
[ ] Dois projetos Google Cloud criados, com faturamento vinculado
[ ] Banco de dados provisionado nos dois projetos
[ ] Arquivos de configuração ajustados e publicados no repositório
[ ] Base de implantação preparada (dois ambientes)
[ ] Segredos do GitHub configurados
[ ] Aprovação obrigatória de produção configurada (Etapa 5)
[ ] Primeira implantação de teste confirmada com sucesso
[ ] Permissões internas concedidas nos dois projetos
[ ] Login configurado (teste e produção, credenciais separadas)
[ ] Credenciais de login guardadas no cofre (dois ambientes)
[ ] Primeiro administrador criado
[ ] Ambiente de teste validado — login e área administrativa funcionando
[ ] Atualização de produção aprovada manualmente (Etapa 13)
[ ] Ambiente de produção validado — login e área administrativa funcionando
```

---

## Em caso de dúvida

Alguns pontos merecem atenção especial ao longo do processo:

- **A ordem das etapas importa.** Cada uma depende do resultado da
  anterior — vale a pena confirmar que uma etapa foi concluída com
  sucesso antes de iniciar a próxima.
- **Os comandos são seguros para repetir.** A maioria das operações
  deste manual pode ser executada novamente sem causar duplicidade ou
  efeito colateral, caso seja necessário refazer algum passo.
- **Nada aqui afeta sistemas fora dos dois projetos criados.** Se algo
  não sair como esperado, o ambiente pode ser recriado do zero sem
  risco para qualquer outro recurso da sua organização.

Para qualquer dúvida durante a execução, entre em contato com nossa
equipe em **{e-mail ou canal de suporte}**.

---

## Próximos passos

Com a aplicação no ar, o próximo passo é liberar o acesso de leitura
aos projetos Google Cloud que você deseja observar — um processo
separado e igualmente simples, coberto em um manual complementar
fornecido à parte.
