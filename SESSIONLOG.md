# SESSIONLOG — Observability Hub

Arquivo de continuidade de sessão. Atualizado pelo Claude Code antes de resets.
Lido obrigatoriamente no início de cada nova sessão após um reset.

---

## Status atual

**Última atualização:** 2026-08-18 — sessão de implementação do domínio
`storage` (Cloud Storage), do zero até deployado em produção, 4 itens
completos, **sprint fechada de ponta a ponta**; seguida, na mesma
sessão, de um gate de aprovação manual pro deploy de app em prod
(pedido do usuário) e de uma auditoria completa da documentação de
acesso/hospedagem (ver seção "CI/CD: gate de aprovação manual em prod +
auditoria de documentação" abaixo — achou e corrigiu lacunas reais,
incluindo um requisito obrigatório de nomenclatura de projeto GCP que
nunca tinha sido documentado como obrigatório). Sessão anterior
(2026-08-17) tinha reconstruído este arquivo depois de 4 dias sem
atualização (ver seção "Storage — domínio novo" abaixo, "Falha de
processo" — os commits dessa reconstrução ficaram presos numa branch
errada e quase se perderam de novo; corrigido nesta sessão com um merge
explícito).

**Estado real agora:** domínio `storage` (Cloud Storage) implementado
por completo — catálogo de buckets, scanner de desperdício (config +
uso real via audit log), extensão do lineage (bucket como nó). Todos os
4 itens validados em dev pelo usuário, incluindo o grafo de lineage real
(`RAW.crm_leads_staging` com bucket `landing` upstream e `processed`
downstream, jobs LOAD/EXTRACT reais). Infraestrutura de prod promovida
(IAM cross-project completo das duas roles de storage, 3 buckets mock
espelhando dev, dados reais, Data Access audit log habilitado — decisão
do usuário, também em prod, não só dev). **PR #25 aberto e mergeado em
`main`**; deploy automático de prod confirmado verde (`gh run list`) e
as duas rotas novas (`/api/v1/storage/.../buckets`,
`/api/v1/storage/.../waste-candidates`) e o `LineageNode` com
`type`/`bucket_name` confirmados no ar via `/openapi.json` de prod.

**Item resolvido nesta sessão**: a mudança não commitada em
`infra/terraform/modules/cloud-run/variables.tf` (`max_instance_count`
2→5, registrada como pendente na atualização anterior) foi **descartada**
por decisão do usuário (`git restore`) — sem justificativa encontrada
nos logs do Cloud Run (nenhum sinal de estar batendo no teto de 2
instâncias), não fazia parte de nenhum trabalho desta sessão.

Ver a seção "Storage — domínio novo" abaixo pra todo o detalhe técnico
(decisões de desenho, bugs reais encontrados em dev, payloads reais de
audit log capturados). As seções anteriores (Sprint 3.2, FinOps, Admin
ACL, Documentação para cliente) continuam válidas — nada mudou nelas
nesta sessão, só ficaram mais antigas na lista.

**Próximo passo:** nenhum pendente desta sprint — está fechada por
completo (dev, prod, PR, deploy, docs). Validação visual das 4
funcionalidades em prod fica a cargo do usuário (sem ferramenta de
browser neste sandbox, mesma limitação de sempre). Candidatos pra
próxima sprint estão em "Backlog"/"Próxima sprint" abaixo, nenhum
aprovado ainda.

---

## Storage — domínio novo (Fase 5, branch `feat/storage-mvp`, concluída)

Primeira expansão do Hub pra além do BigQuery — spec completa em
`docs/specs/storage.md` (v1.0 → v1.1 ao longo desta sessão). Regras de
execução (mesmas de sempre, confirmadas no início): plano resumido antes
de cada item, `pytest` depois de cada domínio backend tocado, testar em
dev antes do próximo item, commit por item, push só com aprovação
explícita a cada vez, sem PR pra `main` até os 4 itens validados.

### Decisões de abertura (seção 10 da spec)
Três pontos abertos, confirmados com o usuário antes de qualquer código:
nome do domínio `domains/storage` (sem colisão encontrada no repo),
rótulo da sidebar "Cloud Storage" (não "GCS"), threshold default do
waste scanner 60 dias. Branch `feat/storage-mvp` a partir de `main`
atualizada (local estava desatualizada, `git fetch && git pull`
necessário antes de criar a branch).

### Item 1 — Catálogo de buckets (commits `02adc81`, `133736f`)
`GET /api/v1/storage/{project}/buckets`. `core/storage_client.py` novo
(client + cache TTL 5min de listagem de objetos, mesmo padrão de
`core/bigquery.py`). `has_lifecycle_rule` via `bucket.lifecycle_rules`;
tamanho total/contagem via listagem de objetos (não há campo agregado
nativo no bucket). Novo `SidebarServiceGroup` "Cloud Storage".

**Bug real em dev**: `roles/storage.objectViewer` (única role prevista
na v1 da spec) devolveu 403 mesmo concedida — `gcloud iam roles describe`
confirmou que ela cobre só `storage.objects.*`/`storage.folders.*`/
`storage.managedFolders.*`, **sem** `storage.buckets.list`/`storage.
buckets.get`. `list_buckets()` (a primeira chamada do domínio) precisa
também de `roles/storage.bucketViewer` (role dedicada, só metadado de
bucket). Corrigido no handler de 403 (`StorageAccessDeniedError` sugere
as duas juntas) e no checklist de `docs/onboarding-cliente.md`. Grant
self em dev confirmado ao vivo via `gcloud projects get-iam-policy`
depois do usuário rodar o comando.

### Item 2 — Freshness: implementada, validada, depois descartada (commits `98bee27`, `7dd64e0`)
V1: endpoint dedicado (`GET .../buckets/{bucket}/freshness`), botão "Ver
freshness" sob demanda (mesmo padrão de `PartitionsDialog` do catálogo),
`last_modified` = `max(customTime ou updated)` entre os **objetos** do
bucket. Implementada e validada em dev — e então o usuário pediu pra
trocar por algo mais simples: `time_created`/`updated` do próprio
`Bucket` (metadado nativo, já vem de graça no `list_buckets()` do item
1) como duas colunas direto na tabela, sem endpoint/dialog separado.

Diferença semântica registrada explicitamente na spec (seção 5):
`Bucket.updated` é quando a **configuração** mudou (lifecycle, storage
class...), não quando um objeto foi gravado — não é o mesmo sinal que a
v1 media (atividade real de dado). Trade-off (mais barato, menos
preciso) aceito conscientemente. Código da v1 removido por completo
(endpoint, `get_bucket_last_modified`, `BucketFreshnessDialog.tsx`,
`useBucketFreshness`) — não deixado como dead code.

### Item 3 — Scanner de desperdício, duas rodadas (commits `381c30b`, `14c6b74`, `f3e352e`)

**Rodada 1 (6.1, config-based)**: bucket sem lifecycle rule + objetos
`STANDARD` mais antigos que o threshold (`IntEnum` 30/60/90, mesma
correção de `Literal`→422 já feita no FinOps). Faixa de economia (nunca
valor único) sobre bytes reais: migração pra `NEARLINE` (mínimo) ou
`COLDLINE` (máximo) — `ARCHIVE` fica de fora de propósito (retrieval
caro + duração mínima de 365 dias tornariam a recomendação automática
arriscada). Preços GCS novos em `core/config.py`, mesmo padrão dos
preços do BigQuery já lá.

**Gap pré-existente corrigido junto** (não era novo deste item):
`list_bucket_objects_cached` não capturava `Forbidden` — um projeto com
`bucketViewer` mas sem `objectViewer` estourava 500 cru em vez do 403
limpo do domínio. `repository.py` ganhou `project_id` nos parâmetros de
listagem de objetos pra relançar `StorageAccessDeniedError`.

**Rodada 2 (6.2, usage-based)** — depois do usuário habilitar Data
Access audit log `DATA_READ` pra `storage.googleapis.com` em dev
(2026-08-18, confirmado ao vivo): objeto elegível por 6.1 sem nenhuma
leitura (`storage.objects.get`) em 90 dias ganha `confidence:
"usage_confirmed"`. Payload do audit log de GCS confirmado ao vivo
(gerei uma leitura real do objeto + `gcloud logging read`): é o proto
padrão `google.cloud.audit.AuditLog` (`resource.type="gcs_bucket"`) —
**diferente** do formato legado `AuditData`/`jobCompletedEvent` que
lineage/access usam pra job do BigQuery, parser novo (`list_read_object_
keys`), mesmo client de Cloud Logging (roles já cross-granted, nenhuma
role nova).

**Ponto de desenho confirmado com o usuário antes de codar**: `Waste
Candidate` é agregado por bucket (validado em dev no item anterior), mas
a spec fala de confidence por **objeto** — resolvido com dois campos
novos (`usage_confirmed_object_count`/`usage_confirmed_size_bytes`,
subconjunto do total elegível) e `confidence` só vira `"usage_confirmed"`
quando **todos** os objetos elegíveis do bucket estão sem leitura
confirmada. Degradação graciosa obrigatória (pedida explicitamente):
`Forbidden` ou resultado vazio pro projeto inteiro (audit log pode estar
desabilitado, ambíguo) nunca falha a requisição — cai pra
`config_based` em todos os candidatos, com `usage_check_warning`
explicando por quê.

### Item 4 — Extensão do lineage: bucket como nó (commit `9bafbee`, maior risco da sprint)
`load` (GCS→BQ) → aresta bucket→tabela; `extract` (BQ→GCS) → aresta
tabela→bucket. Os dois payloads reais (seção 7.1 da spec) foram usados
como fixture de teste, não inventados — confirmados ao vivo em dev antes
de escrever qualquer parser.

**Ponto de desenho que exigiu pausa** (conforme pedido explícito do
usuário no início do item): diferente de tabela, um bucket não tem
"projeto dono" confiável via API pra saber em qual audit log procurar
quem mais o referencia. Resolvido com o usuário: **bucket é sempre nó
folha** — entra no grafo (nó + aresta) quando descoberto pelos eventos
já buscados do lado tabela (sem chamada nova), mas a travessia BFS nunca
expande a partir dele. `NodeRef` (service.py) generaliza `TableRefTuple`
(3-tupla) + `BucketRef` (1-tupla), discriminável só pelo tamanho da
tupla. `LineageNode` ganhou `type`/`bucket_name`;
`project_id`/`dataset_id`/`table_id` viraram opcionais. Frontend:
`bucketNode` novo em `LineageGraph.tsx` (ícone `HardDrive`, cor
`status-ok`, mesma identidade do grupo "Cloud Storage" da sidebar).

**Gap encontrado, deliberadamente não corrigido** (fora do escopo —
é do domínio `lineage` inteiro, não específico de bucket): nenhum parser
de audit log do projeto (lineage/access/finops) filtra `jobStatus.state
!= "DONE"` — um job que falhou mas tem `destinationTable`/`sourceUris`
no config já criaria uma aresta hoje. Registrado como backlog do domínio
lineage, não do domínio storage.

**Validado em dev pelo usuário**: lineage de `RAW.crm_leads_staging`
mostrou bucket `observability-hub-dev-landing` upstream (via LOAD real)
e `observability-hub-dev-processed` downstream (via EXTRACT real), com o
estilo visual diferenciado e sem seta de expansão nos nós de bucket.

### Falha de processo encontrada e corrigida nesta sessão
Os 4 commits de fechamento do SESSIONLOG/CHANGELOG de uma sessão
anterior (reconstrução completa depois de 4 dias sem atualização — ver
"Documentação para cliente" mais abaixo pro contexto) tinham sido
pusheados só pro remoto de `feature/admin-usage-analytics`, **nunca
mergeados em `main` via PR**. Quando `feat/storage-mvp` foi criada a
partir de `main` atualizada (que não inclui esses 4 commits), herdou a
versão **velha** do SESSIONLOG (2026-08-14) — quase repetindo a mesma
falha que aquela reconstrução tinha corrigido. Descoberto no meio desta
sessão (ao notar que o CHANGELOG.md não tinha as seções que eu mesmo
tinha escrito antes), corrigido com `git merge feature/admin-usage-
analytics` explícito em `feat/storage-mvp` antes de qualquer atualização
final de documentação (commit `96c4db4`) — só um conflito real, na
tabela de registro de acessos do `docs/onboarding-cliente.md` (as duas
branches adicionaram linhas diferentes na mesma tabela), resolvido
mantendo as duas.

**Lição registrada aqui de propósito**: commits de documentação
"soltos" numa branch de feature, sem PR, são tão frágeis quanto nenhuma
documentação — o processo só é confiável quando o merge pra `main`
acontece de verdade. Considerar, numa sessão futura, abrir PRs só de
docs quando uma branch de feature demorar muito pra fechar (em vez de
esperar o PR final que empacota tudo junto).

### Promoção pra prod — concluída nesta sessão (antes do PR pra `main`)
Checklist passado ao usuário fora deste arquivo, ele confirmou ter
rodado (parte em paralelo comigo, parte eu mesmo rodei quando pedido
diretamente) — tudo confirmado ao vivo depois, não assumido:
1. ✅ IAM self: `backend-run@...-prod` ganhou `roles/storage.
   bucketViewer` + `roles/storage.objectViewer` em `observability-hub-
   prod`.
2. ✅ IAM cross (mesmo padrão simétrico já usado pra BigQuery/Logging):
   `backend-run@...-dev` ganhou as mesmas duas roles em
   `observability-hub-prod`; `backend-run@...-prod` ganhou as mesmas
   duas roles em `observability-hub-dev`. Confirmado via `gcloud
   projects get-iam-policy` nos dois projetos — matriz 2×2 completa
   (2 roles × 2 SAs × 2 projetos).
3. `storage.googleapis.com` já estava habilitada em prod antes desta
   sessão (confirmado via `gcloud services list` — provavelmente
   habilitada como dependência de outra coisa, não documentado quando).
4. ✅ 3 buckets mock em prod, espelhando dev exatamente: `observability-
   hub-prod-landing` (STANDARD, mesma lifecycle rule de dev —
   `SetStorageClass NEARLINE` aos 30 dias por `customTime`),
   `observability-hub-prod-processed` (NEARLINE, sem regra),
   `observability-hub-prod-archive` (COLDLINE, sem regra, vazio).
5. ✅ 1 objeto mock em `landing` (mesmo conteúdo do de dev), 1 job LOAD
   real (`landing` → `RAW.crm_leads_staging`, tabela nova — prod já
   tinha `RAW.crm_leads`, sem `_staging`) e 1 job EXTRACT real
   (`crm_leads_staging` → `processed`) — confirmados via `bq show`/
   `gcloud storage ls` ao vivo.
6. ✅ **Decisão do usuário**: habilitar Data Access audit log
   `DATA_READ` de `storage.googleapis.com` **também em prod** (não só
   dev) — diferente do planejado inicialmente (a spec, seção 6.2,
   registra a nota de volume/custo — evento por leitura de objeto — como
   motivo pra adiar; o usuário decidiu prosseguir mesmo assim,
   consciente do trade-off). Aplicado via merge de `auditConfigs`
   (mesmo padrão de `docs/onboarding-cliente.md` seção 3), sem
   sobrescrever a config existente de `bigquery.googleapis.com`.
   Confirmado via `gcloud projects get-iam-policy` — as duas entradas
   coexistem.
7. ✅ Tudo registrado em `docs/onboarding-cliente.md` (6 linhas novas na
   tabela "Registro de acessos concedidos").

**PR #25 aberto e mergeado em `main`** no mesmo dia, a pedido explícito
do usuário. Deploy automático de prod confirmado verde (`gh run list`)
e as rotas novas confirmadas no ar via `/openapi.json` de prod.

### Status final
- Backend: 597 testes unitários (0 quando o domínio começou), 100%
  passando, `ruff check`/`ruff format` limpos em cada commit.
- Frontend: `biome check`, `tsc -b`, `vite build` limpos em cada commit.
- Validado em dev pelo usuário — os 4 itens, incluindo o grafo de
  lineage com bucket real.
- Prod promovida por completo (IAM, buckets, dados mock, audit config)
  antes do merge — ver seção acima.
- **PR #25 mergeado, deploy de prod verde. Sprint fechada.**

---

## CI/CD: gate de aprovação manual em prod + auditoria de documentação

Trabalho direto em `main`, depois da sprint do domínio storage, sem
sprint formal — dois pedidos separados do usuário na mesma sessão.

### Gate de aprovação de prod (commit `6e2d506`)
Pedido do usuário depois de investigar um custo de Cloud Run acima do
normal (ver abaixo). Brainstorm de opções (workflow_dispatch puro vs.
GitHub Environment com approval vs. desacoplar build de deploy) —
usuário escolheu a opção 2: `backend-deploy-prod.yml`/`frontend-deploy-
prod.yml` ganharam `environment: production` no job de deploy, GitHub
segura em "Waiting" até aprovação manual. `terraform-apply-prod.yml`
fica de fora, de propósito (infra já passa por plan revisado antes do
merge). `dev` não muda.

**Corrida de tempo na primeira aplicação**: o usuário configurou o
environment "production" (Settings → Environments, required reviewers)
enquanto os dois workflows do push seguinte já estavam rodando —
`backend-deploy-prod` ficou corretamente em "Waiting", mas
`frontend-deploy-prod` já estava `in_progress` e terminou sem gate
(deploy único sem aprovação, não repetido). Backend foi aprovado
manualmente pelo usuário depois (eu não aprovei — é exatamente o tipo
de ação que o gate existe pra exigir de um humano).

### Diagnóstico de custo do Cloud Run (achado no caminho)
Usuário perguntou como o Cloud Run é cobrado e por que um dia custou
mais que os outros. Investigação ao vivo:
- `min_instance_count = 0` (scale-to-zero) confirmado intacto nos 4
  serviços (dev/prod × backend/frontend) — nunca foi o problema.
- **Achado real**: os 4 serviços estavam com `run.googleapis.com/
  cpu-throttling: false` ("CPU sempre alocada") — não vinha do Terraform
  (`resources.cpu_idle` não declarado no módulo `cloud-run`) nem dos 4
  workflows de deploy (nenhum passa essa flag) — mudado manualmente fora
  do fluxo do projeto, sem registro de quando/por quê/quem. Revertido
  pro padrão (CPU só durante request) nos 4, confirmado
  `cpu-throttling: true` + health check 200 nos 4 depois do rollout.
- Contagem de requests do dia mais caro (dev 1163, prod 37) bateu com um
  dia de implementação intensa (a própria sprint de storage) — não foi
  vazamento de tráfego, foi o multiplicador de custo do CPU sempre
  alocado em cima de um dia de uso real alto.
- TanStack Query do frontend não gera tráfego de fundo com abas abertas
  sem foco por padrão (`refetchIntervalInBackground` é `false`, único
  uso de `refetchInterval` é o badge de admin a cada 60s) — confirmado
  lendo `query-client.ts`/`features/admin/hooks.ts`, não assumido.

### Auditoria completa de documentação de acesso e hospedagem
Pedido explícito: revisar de ponta a ponta tudo que vai ser entregue a
terceiros (liberar acesso a projeto-alvo) e usado pelo próprio usuário
pra hospedar o Hub do zero em outra conta GCP e outro repositório
GitHub — "tudo precisa estar 100% pronto e funcional, sem nada
faltando".

**Achados, todos corrigidos:**
1. `docs/playbooks/liberar-projeto-para-o-hub.md` e `docs/manual-
   liberacao-acesso-cliente.md` **não mencionavam o domínio storage em
   nenhum lugar** — escritos antes da Fase 5 (PRs #22-24, antes de
   `feat/storage-mvp`), nunca atualizados depois. Faltavam a API
   `storage.googleapis.com`, as duas roles (`storage.bucketViewer`/
   `storage.objectViewer`, sempre juntas — mesma pegadinha do par
   `logging.viewer`/`logging.privateLogViewer`) e o audit log opcional
   de `storage.googleapis.com` com o aviso de volume. Adicionado por
   completo nos dois (seção técnica + versão em linguagem de cliente),
   incluindo checklist e troubleshooting.
2. `docs/onboarding-cliente.md`: introdução citava só 4 dos 8 domínios;
   a tabela de roles não creditava `pii`/`access`/`finops` como
   consumidores das mesmas roles já listadas (davam a entender, por
   omissão, que só catalog/freshness/quality/lineage precisavam delas);
   a justificativa de "`billing.viewer` não necessário" ainda dizia
   "domínio FinOps não implementado" — implementado há dias, a razão
   real é que FinOps usa audit log + preço público, nunca Billing
   Export. Todos corrigidos.
3. **Achado crítico, nos dois documentos de hospedagem** (`hospedar-hub-
   em-novo-projeto.md`, `manual-implementacao-cliente.md`): a escolha de
   nome dos dois projetos GCP novos nunca foi documentada como
   **obrigatória** terminar em `-dev`/`-prod` — só aparecia como exemplo
   sugerido (`acme-hub-dev`/`acme-hub-prod`), dando a impressão de que
   era só uma convenção de nomenclatura. Na prática,
   `core/secrets.py::_is_prod()` decide qual par de secrets OAuth ler
   checando literalmente `project_id.endswith("-prod")` — o único lugar
   do código que depende disso, mas se os nomes escolhidos não seguirem
   esse padrão, o backend de "prod" leria os secrets de "_DEV" pra
   sempre, **sem erro nenhum**, e o login falharia de um jeito confuso de
   debugar. Promovido de "exemplo" pra aviso obrigatório (⚠️) + item de
   checklist + linha de troubleshooting nos dois documentos.
4. Os dois playbooks de hospedagem também ganharam o passo de configurar
   o `environment: production` do GitHub (ver seção de CI/CD acima) —
   replicar o repositório copia os workflows já com `environment:
   production` no YAML, mas sem a regra de proteção configurada nas
   Settings do novo repositório, o gate simplesmente não existe (nenhum
   erro, só não bloqueia nada).

Nenhuma mudança de código nesta parte da sessão — só documentação.
`CHANGELOG.md` ganhou as duas seções correspondentes (CI/CD + auditoria)
no mesmo padrão de sempre.

---

## Sprint 3.2 — Qualidade, Discovery e melhorias de UX (concluída, 7/7 — PR #18)

Branch `feat/sprint-3.2`, a partir de `main` (`44ad7c9`, pós-merge do PR
#17). Regras definidas pelo usuário no início da sprint: pytest depois de
cada domínio de backend, testar em dev depois de cada item, commitar na
branch (push só com aprovação explícita a cada vez), sem PR pra `main`
até os itens completos e validados, plano apresentado antes de qualquer
arquivo novo.

### Filtros e ordenação (commits `5516b36`, `dae151e`)
`AssetsTable` (catálogo) e `TableFreshnessTable` (freshness por tabela,
dentro de um dataset) ganharam busca por nome + filtro por tipo/status
SLA + colunas ordenáveis client-side (`useMemo`, sem mudança de
backend). Componente `SearchSortableHead` (já existia só na busca) foi
promovido pra `components/SortableTableHead.tsx` compartilhado. Descobriu-
se nessa hora que `DatasetFreshnessTable` (a tabela de *datasets*, na
raiz de `/freshness` — diferente de `TableFreshnessTable`) já existia sem
filtro nenhum; ganhou o mesmo tratamento depois, a pedido do usuário.

### Score de qualidade — implementado e depois removido (commits `695f9e1`,
`3b12689`, revert `59d4ae8`)
Implementado por completo: `core/sla.py` (SLA extraído de `freshness` pra
ser compartilhado com `quality`), `domains/quality/score.py` (média
ponderada — completude 40%, freshness 30%, duplicatas 20%, documentação
10%, valor neutro 50 nas três primeiras quando não há dado), persistência
do último profiling em Firestore (`profiling_results/
{project}_{dataset}_{table}`, coleção compartilhada — decisão consciente
pra não depender de quem rodou o profiling), endpoint `GET /api/v1/
quality/score/...`, badge colorido + tooltip com breakdown na
`AssetsTable`. **Validado em dev pelo usuário** — e então removido por
completo (revert manual preservando `core/sla.py`, que é refatoração
independente do score) a pedido explícito do usuário. `profiling_results`
não é mais escrito por nenhum código a partir deste commit; pode haver
documentos órfãos remanescentes no Firestore de dev de quando a feature
esteve ativa (ver "Backlog").

### Histórico de qualidade (commits `89796d2`, `6efeaa2`)
Cada profiling grava um snapshot em `profiling_history/
{project}_{dataset}_{table}/runs/{auto-id}` (Firestore, coleção
compartilhada, máximo 30 runs por tabela — mesmo padrão de trim-to-max de
`domains/history`, adaptado pra subcoleção em vez de coleção plana).
Endpoint `GET /api/v1/quality/history/...`. `run_profiling()` recuperou
os parâmetros `firestore_client`/`executed_by` que tinham sido removidos
no revert do score (agora servem o histórico). Frontend: aba "Histórico"
no modal de profiling — gráfico de linha (`recharts`, dependência nova)
com densidade ao longo do tempo, tabela de runs com linha expansível
mostrando completude por coluna, alerta quando a densidade cai mais de 10
pontos percentuais em relação ao run anterior. `useRunProfiling` invalida
a query de histórico ao concluir um run, pra aba atualizar sem fechar o
modal. **Validado em dev pelo usuário.**

### Lineage e tabelas órfãs (commits `12d6d9b`, `28f1f7f`)
Novo `domains/lineage/`, fonte de dados são audit logs de job completado
do BigQuery via Cloud Logging (formato `BigQueryAuditMetadata`/
`jobChange`, documentado em docs.cloud.google.com/bigquery/docs/reference/
auditlogs/migration — **schema do payload ainda não validado contra logs
reais** porque os Data Access audit logs continuam desabilitados em dev e
prod, ver "Backlog"). `referencedTables`/`destinationTable` de cada job na
janela de 30 dias reconstroem upstream/downstream de uma tabela e a lista
de órfãs de um projeto (tabela sem nenhum job que a referencie como
leitura). Limitação registrada explicitamente na API: não dá pra
distinguir "sem atividade" de "audit logs desabilitados" só pelo
resultado — quando vem vazio, a resposta inclui um campo `warning` com
instruções em vez de afirmar uma certeza que a implementação não tem.
Falta de `roles/logging.viewer` vira `LoggingAccessDeniedError` → 403 com
o comando `gcloud` pronto (mesmo padrão de `ProjectAccessDeniedError`).

Endpoints: `GET /api/v1/lineage/{project}/{dataset}/{table}` e
`GET /api/v1/lineage/{project}/orphans`. Frontend: aba "Lineage" no modal
de profiling, página "Tabelas órfãs" (rota `/orphans`, link na sidebar),
novo `components/ApiErrorNotice.tsx` compartilhado que mostra os comandos
de `error.body.fix` quando presentes — corrigiu de quebra o tipo de
`ApiErrorBody.fix` (já era array em runtime, estava tipado como
`string`). **Ainda não validado visualmente em dev pelo usuário** — só
testado via suíte de testes (23 novos) e build limpo. Como os audit logs
estão desabilitados, o comportamento esperado em dev agora é: aviso
amarelo em toda consulta, e a página de órfãs listando todas as tabelas
do projeto (esperado dada a limitação de visibilidade, não é bug).

### Bug: lineage cross-project dava "Failed to fetch" (commit `c33f950`,
sessão de 2026-08-14 depois de `d9401d2`)
Usuário validou lineage/órfãs em dev (projeto nativo, ok) mas achou "Failed
to fetch" ao trocar pra olhar o projeto prod com o Hub rodando em dev.
Causa raiz, confirmada nos logs reais do Cloud Run de dev
(`gcloud logging read ... severity>=ERROR`): `domains/lineage/repository.py`
capturava `google.api_core.exceptions.PermissionDenied` (classe de erro
gRPC), mas o client do Cloud Logging usa transporte REST
(`_use_grpc=False`, ver docstring de `core/logging_client.py`) — um 403 via
REST levanta `Forbidden`, não `PermissionDenied`. A exceção real escapava
sem tratamento, virava 500 não capturado por nenhum `@app.exception_handler`,
e por estar fora do `CORSMiddleware` nesse caminho o browser reportava
"Failed to fetch" em vez do 403 tratado que `LoggingAccessDeniedError` já
sabia gerar. Resto do backend já usava a classe certa (`core/bigquery.py`,
`domains/quality/repository.py`); só lineage tinha o import errado.
Corrigido trocando `PermissionDenied` por `Forbidden` no import e no
`except`; testes do módulo (que mockavam `PermissionDenied`, mascarando o
bug) corrigidos pra mockar `Forbidden`. 303 testes passando, ruff limpo.

Enquanto investigava, descobri que `roles/logging.viewer` (self) e os
Data Access audit logs do BigQuery já estavam habilitados nos dois
projetos desde antes desta sessão, sem nunca terem sido documentados aqui
— ver correção dos itens 8/9/10 do Backlog. A pedido do usuário, concedi
(ele rodou via `!`) `roles/logging.viewer` cross-project nos dois sentidos
(dev→prod e prod→dev) — mesmo padrão das roles de BigQuery já cross-granted
desde a Sprint 2. Confirmado ao vivo via `gcloud projects get-iam-policy`
depois do comando.

### Bug 2: lineage cross-project não estourava mais erro, mas retornava
sempre vazio (`roles/logging.privateLogViewer` faltando, mesma sessão)
Usuário revalidou depois do fix acima — "Failed to fetch" resolvido, mas
a mensagem virou o aviso estático de "nenhum evento encontrado nos audit
logs" pra `observability-hub-prod`, apesar de `auditConfigs` já estarem
habilitados (confirmado no Bug 1 acima). Suspeita inicial (dado
insuficiente/quantidade de eventos) descartada rodando a query real via
`gcloud logging read` como usuário: **11.298 entradas** de
`jobservice.jobcompleted` em prod nos últimos 30 dias, muito longe de
"sem atividade". Reproduzindo `repository.list_job_events` localmente com
essas credenciais (usuário, não a SA), os 11.298 eventos parseavam sem
problema — ou seja, o parser está correto, o bug é puramente de IAM.

Causa raiz, confirmada contra a documentação oficial do GCP
(`docs.cloud.google.com/logging/docs/access-control`): **Data Access
audit logs exigem `roles/logging.privateLogViewer` pra serem visíveis via
API, além de `roles/logging.viewer`** — Admin Activity/System Event/Policy
Denied logs bastam com `logging.viewer`, mas Data Access (categoria onde
vive o `jobCompletedEvent` que lineage lê) é mais restrita por design
(pode conter informação sensível sobre o que foi acessado). Sem
`privateLogViewer`, a chamada **não falha** — só retorna sempre vazio,
indistinguível de "sem atividade real" ou "audit logs desabilitados" só
pelo resultado. `roles/logging.privateLogViewer` já existia self (cada SA
no próprio projeto, daí dev-olhando-dev sempre ter funcionado) mas nunca
tinha sido cross-granted — só `logging.viewer` foi cross-granted no Bug 1
acima, o que bastou pra não estourar 403 mas não bastou pra ver os dados.

Corrigido em três frentes:
1. `domains/lineage/service.py::_EMPTY_RESULT_WARNING` reescrito pra
   mencionar as duas roles como causa possível, não só "audit logs
   desabilitados" (que era a única hipótese sugerida antes, incompleta).
2. `main.py::handle_logging_access_denied` (o 403 de
   `LoggingAccessDeniedError`, que dispara quando falta `logging.viewer`
   por completo) passou a sugerir as duas roles de uma vez, mesmo padrão
   de `ProjectAccessDeniedError`.
3. `docs/onboarding-cliente.md` corrigido — a primeira versão do
   documento (escrita mais cedo nesta mesma sessão, antes deste bug
   aparecer) tinha marcado `logging.privateLogViewer` como "não usada
   pelo código, não replicar em onboarding"; agora faz parte do
   checklist oficial, com nota de correção explicando o erro.

Comandos de `roles/logging.privateLogViewer` cross-project (dev→prod e
prod→dev) fornecidos ao usuário nesta sessão — **pendente confirmação de
execução e revalidação em dev**, ver `docs/onboarding-cliente.md` pra o
comando exato e o registro de quando for confirmado.

Nesta mesma sessão, criado `docs/onboarding-cliente.md` (checklist
completo de IAM/API/audit config pra um projeto cliente aceitar leitura do
Hub) e nova seção "Registro de acessos e configurações" no CLAUDE.md,
pedindo que toda concessão de acesso futura (IAM, API, audit config, em
qualquer projeto incluindo dev/prod um observando o outro) seja registrada
naquele documento no momento em que acontece — mitigação direta da falha
de processo que causou os itens 8/9/10 ficarem desatualizados.

### Ajustes de UX e correção de bug no catálogo (commits `355b4f7`, `2af5a14`)
`355b4f7`: contextos de query (TanStack Query) do domínio lineage
passaram a ser prefixados com `project_id` — sem isso, trocar de projeto
no seletor sem sair da página podia mostrar lineage cacheado do projeto
anterior (mesmo bug de classe já visto em outros domínios, corrigido
aqui especificamente pra lineage). `2af5a14`: botões "Analisar"/"Ver
partições" no catálogo ficaram sempre visíveis nas linhas da tabela (não
só no hover) — usuários em touch/trackpad reportaram dificuldade de
descobrir a ação.

### Lineage v2 — cadeia transitiva multi-hop, cross-project, diagrama (commit `6d7b742`)
Reescrita de `domains/lineage/service.py`: a v1 (1-hop, já documentada
acima) virou uma travessia **BFS bidirecional** a partir da tabela raiz,
com `max_hops` configurável via query param (default 8, máx 15,
independente por direção upstream/downstream — alcance total até
`2 × max_hops`). Diferenças de fundo em relação à v1:

- Toda comparação de tabela passou a usar a tripla completa
  `(project_id, dataset_id, table_id)`, nunca só `(dataset_id,
  table_id)` — a v1 tinha um bug latente de colisão entre projetos
  diferentes com dataset/tabela de mesmo nome, nunca disparado em dev/
  prod (só 2 projetos, nomes não colidiam) mas real.
- A travessia pode atravessar **mais de um projeto GCP** durante a
  expansão do grafo — cada projeto novo encontrado é consultado no
  máximo uma vez por requisição (cache em memória por request). Não é
  mudança de modelo de acesso (ADR-006 já previa a SA do Hub com acesso
  simultâneo a vários projetos-alvo) — é só um padrão de uso novo sobre
  um acesso que já existia.
  - Projeto **raiz** sem `roles/logging.viewer`/`privateLogViewer`:
    HTTP 403 (hard-fail, igual v1 — sem a raiz não há nada pra montar).
  - Projeto **não-raiz** sem acesso, encontrado durante a expansão: nó
    marcado `access_denied=true`, esse ramo não expande, resto do grafo
    segue intacto — não derruba a requisição inteira.
- `JOIN` com múltiplas fontes vira fan-in natural no grafo (duas arestas
  convergindo no mesmo nó) — não precisou de tratamento especial.
- Auto-referência (job tipo MERGE que lê e escreve a própria tabela)
  nunca vira aresta, em nenhum hop — mesma exclusão da v1, agora
  aplicada uniformemente em toda a travessia.
- `truncated: true` na resposta quando `max_hops` foi atingido com
  fronteira ainda não expandida (pode haver mais tabelas além do
  retornado).

Frontend: dependências novas `@xyflow/react` + `dagre` (+ `@types/dagre`)
pra renderizar o grafo como diagrama interativo (layout automático via
`dagre`) na aba "Lineage" do modal de profiling — antes era só duas
listas (upstream/downstream). Ver spec completa em `docs/specs/lineage.md`
v2.0 (formaliza retroativamente também o comportamento da v1, que nunca
teve spec própria).

### PII — fingerprinting via TABLESAMPLE + heurística de nome (commit `341a431`)
Novo `domains/pii/`, duas camadas independentes:

1. **Heurística de nome** (grátis, `INFORMATION_SCHEMA.COLUMNS` apenas)
   — substring case-insensitive do nome da coluna contra keywords por
   tipo de PII (ex: `num_cartao_cliente` bate `cartao_credito` por
   conter `"cartao"`).
2. **Amostragem real** via `TABLESAMPLE SYSTEM` + `REGEXP_CONTAINS` +
   `COUNTIF` — tipos detectados: email, CPF, CNPJ, telefone BR, CEP,
   cartão de crédito (regex de **formato**, sem validação de dígito
   verificador nem algoritmo de Luhn — falso positivo/negativo é
   limitação conhecida e documentada). **Garantia estrutural de
   privacidade**: o matching roda inteiro dentro do BigQuery — a API
   nunca recebe, processa ou loga um valor de coluna real, só contagens
   agregadas por coluna/tipo.

`flagged` por coluna = nome bateu **ou** amostra sinalizou algum tipo;
`confidence` é `high` (os dois bateram), `medium` (só um) ou `null`
(nenhum). Tabela/view: `TABLESAMPLE` não suportado em view — PII **pula
a amostragem inteiramente** nesse caso (diferente de profiling, que
ainda roda sem `TABLESAMPLE`), porque rodar sem amostragem escanearia a
view inteira sem estimativa de custo prévia — só heurística de nome
nesse caso. Endpoints: `POST /api/v1/pii/{project}/{dataset}/{table}/
estimate` (dry run) e `/run` (executa). Cache em memória de 5min por
`(tabela, parâmetros)` evita reexecutar a query paga em cliques
repetidos. Ver `docs/specs/pii.md` v1.1 (a v1.1 adicionou histórico de
scans em `pii_scan_history`, junto com o Admin v1.3 — ver seção Admin
abaixo).

### Status de fechamento parcial (commit `092fa34`, "6 de 7 itens, PII concluído")
Neste ponto só faltava o mapa de acesso — ver próxima seção. Backend:
recharts + xyflow/dagre já em uso; testes crescendo a cada domínio novo.

### Mapa de acesso — 7º e último item da Sprint 3.2 (commits `f6db87d`, `ceff29d`)
Novo `domains/access/`, mesma fonte de dados de lineage (audit logs de
job do BigQuery via Cloud Logging, janela de 30 dias, custo $0) sob um
ângulo diferente: lineage pergunta "de onde vem/pra onde vai esse dado",
mapa de acesso pergunta "quem tocou nessa tabela e quando".
`domains/access/repository.py` duplica o parsing do payload em vez de
importar de `lineage` (nenhum domínio deste projeto importa de outro),
com uma diferença: também extrai `jobStatistics.endTime` como timestamp
do acesso.

`GET /api/v1/access/{project}/{dataset}/{table}` agrega por
`principal_email`: contagem de acessos, tipos (`read`/`write`, um job
pode contribuir os dois — ex: MERGE — e aqui isso **não** é excluído
como em lineage, porque pra mapa de acesso é um acesso real, não uma
relação de dependência entre tabelas), timestamp mais recente, e
`is_service_account` (heurística: e-mail termina em
`gserviceaccount.com`).

**Bug corrigido no mesmo dia (`ceff29d`)**: sem filtro, toda vez que
alguém rodava profiling ou scan de PII pela própria UI do Hub, quem
executa a query real no BigQuery é a SA de runtime do Hub
(`backend-run@<projeto>`), não o usuário — isso fazia a própria SA do
Hub aparecer como "acesso recente" em qualquer tabela inspecionada,
mascarando os consumidores externos reais (o oposto do propósito da
funcionalidade). Fix: todo evento cujo `principal_email` seja
`backend-run@<projeto-onde-o-Hub-está-rodando>.iam.gserviceaccount.com`
é descartado antes de agregar — outras service accounts (pipelines
externos) continuam contando normalmente. Ver `docs/specs/access.md`
v1.0, seção "Exclusão da SA do próprio Hub" — nota explícita de que
`domains/finops` (budget) faz o oposto de propósito: lá a SA do Hub
**conta**, porque a pergunta é "quanto está sendo gasto de verdade",
não "quem é consumidor externo".

### Status no fim da Sprint 3.2 (commit `ceff29d`)
Backend: testes unitários crescendo (556 no total do repositório hoje,
incluindo todo o trabalho posterior de FinOps/Admin — não isolado por
sprint). `ruff check`/`ruff format` limpos em toda a sessão. PR #18
mergeado em `main`/prod em 2026-08-15.

---

## FinOps — as 3 frentes do roadmap (Fase 4, PRs #19, #20, #21)

Reconstruído a partir de `docs/specs/finops-waste-scanner.md` (v1.0),
`docs/specs/finops-budget.md` (v1.1) e `docs/specs/finops-column-types.md`
(v1.1) — nenhuma sessão anterior deixou nota no SESSIONLOG sobre este
trabalho. **`CHANGELOG.md` continua dizendo Fase 4 "em andamento, falta
otimizações sugeridas" — desatualizado, ver Backlog.**

### 1. Scanner de desperdício (commits `a43bb1f`, `a5021a2`; PR #19)
Duas checagens independentes num projeto: **tabelas sem uso** (nunca
lidas, ou não lidas há N dias, nos audit logs — `GET /api/v1/finops/
{project}/unused-tables?min_days_unused=30|60|90`) e **candidatas a
particionamento** (tabelas grandes, sem partição, com coluna
DATE/DATETIME/TIMESTAMP candidata — `GET .../partition-candidates`).
Fonte: Cloud Logging (audit logs, custo $0) + `INFORMATION_SCHEMA`/
`client.get_table()` (metadado, custo $0).

Decisão de design explícita com o usuário: **nunca fabricar um número
de aparência precisa sobre suposição não verificada**. Tabelas sem uso
ganham estimativa **factual** (`size_bytes` × preço de storage — custo
real já sendo pago). Candidatas a particionamento só ganham estimativa
de economia se houver custo **observado de verdade** nos audit logs
(soma de `totalBilledBytes`), e mesmo assim como **faixa** (30–70% de
redução), nunca um valor único — sempre acompanhada de disclaimer
explícito.

**Bug corrigido (`a5021a2`)**: `min_days_unused` usava `Literal[30, 60,
90]` no schema Pydantic, que o FastAPI/OpenAPI não conseguia validar
corretamente via query param — 422 em requisições válidas. Trocado por
`IntEnum`.

### 2. Budget de custo (commits `abf8e28`, `b4ce5d5`, `5481447`, `9cc68b2`; PR #20)
`GET /api/v1/finops/{project}/budget?group_by=table|user|day|month|year`
— sempre relativo ao mês corrente. Mesma fonte de dados do scanner
(audit logs), sem API/role nova. **Decisão de arquitetura documentada
explicitamente**: BigQuery Billing Export foi considerado e rejeitado —
só quebra custo por projeto+SKU, nunca por dataset/tabela, não resolveria
o problema mesmo se configurado.

Nota de precisão registrada na spec: o número é uma **estimativa**
(`totalBilledBytes × preço on-demand`), correta só se o projeto cobra
por bytes escaneados — não reflete o gasto real em projetos flat-rate/
Editions (slots reservados). Mesma premissa on-demand já embutida em
`domains/quality` e no scanner de desperdício, documentada aqui porque
budget é onde um número errado mais provavelmente vira decisão
financeira.

**Diferença deliberada do mapa de acesso**: budget **não** exclui a SA
de runtime do Hub da agregação — profiling/PII rodado pela UI custa
dinheiro de verdade, então deve contar tanto em `group_by=table` quanto
em `group_by=user`.

**Bug real corrigido (`b4ce5d5`)**: agregação por dataset/tabela trazia
entradas fantasma tipo `region-US` com custo residual (~$0,07), sem
corresponder a nenhum dataset real. Investigado com `gcloud logging
read` + replay contra ~5000 eventos reais de dev: **4989 de 5000 jobs
(99,8%)** eram probes de `INFORMATION_SCHEMA` region-qualificado
(`` `project.region-X.INFORMATION_SCHEMA.*` ``, disparadas pela própria
SA do Hub para descoberta de metadados em catalog/freshness/finops) —
o audit log registra `datasetId="region-US"`/`tableId="INFORMATION_
SCHEMA.SCHEMATA"`, indistinguível à primeira vista de uma tabela real
chamada `region-US`. Fix na origem (`repository._parse_table_ref`
descarta qualquer referência cujo `table_id` comece com
`INFORMATION_SCHEMA.`), benefício automático pra scanner de desperdício
e budget juntos. `5481447`: mensagem de "sem acesso" do finops passou a
explicitar a janela de 90 dias + filtro por dataset. `9cc68b2`: retry de
cold start do Cloud Run (já existia em queries) estendido também pra
mutations — cold start em dev podia derrubar a primeira ação do usuário
depois de um tempo ocioso.

Na v1.1 da spec, "top N gastadores" (existia na v1.0 como visão
separada) foi removido — `group_by=user` cobre o mesmo caso sem duplicar
lógica de agregação.

### 3. Sugestão de tipo de coluna (commits `81db4a3`, `15d579e`; PR #20/#21)
Terceira e última frente do roadmap de FinOps. Diferente das outras
duas (100% metadado/audit-log, custo $0), esta amostra dado real via
`TABLESAMPLE` — mesmo mecanismo (e mesmo custo real) de `pii`/`quality`,
por isso exige clique explícito em "Estimar custo" antes de "Escanear",
igual aos outros domínios que tocam dado real.

Por coluna `STRING`, testa em ordem de prioridade (primeiro tipo com
100% de match no não-nulo amostrado vence): `INT64` → `FLOAT64` → `BOOL`
→ `DATE` → `DATETIME` → `TIMESTAMP`, via `SAFE_CAST` (mesma garantia
estrutural de privacidade do PII — só contagens agregadas saem do BQ).
Só sugere quando **as três** condições batem: 100% de match na amostra
(não configurável — aplicar tipo mais estreito que não converte 100%
quebraria dado real), amostra não-vazia, e economia de bytes
**positiva** (uma STRING curta como `"1"` já ocupa menos que um INT64
fixo de 8 bytes — sugerir a troca nesse caso pioraria o storage).

`15d579e` (v1.1) adicionou **escopo explícito de tabelas**
(`ColumnTypeScanRequest.tables`, lista `"dataset.tabela"`) — rodar em
todas as tabelas de um projeto real é inviável (centenas/milhares de
tabelas, cada uma custando uma query real); o frontend sempre manda
escopo explícito nas duas telas onde a feature aparece: aba "Tipos de
coluna" em `/finops` (seletor de datasets/tabelas via checkbox) e uma
aba nova no modal de profiling (escopo implícito: só a tabela aberta).
Orçamento de tempo de 120s pro lote inteiro no `/run` — se esgotar no
meio, retorna parcial com warning em vez de erro.

---

## Sidebar — duas reorganizações (commits `c785c4e`, `94629a6`)

**Round 1 (`c785c4e`, entre waste scanner e budget)**: sidebar agrupado
por tópico — "Buscar tabelas" solto no topo, "Governança" (Freshness +
Tabelas sem consumidor), "FinOps" (Scanner de desperdício, grupo já
pronto pra crescer conforme budget/tipos de coluna viravam abas
próprias). Renomeações: "Busca" → "Buscar tabelas", "Tabelas órfãs" →
"Tabelas sem consumidor" (nome mais descritivo). Favoritos e Recentes
viraram `Collapsible`, mesmo padrão que "Datasets disponíveis" já usava.

**Round 2 (`94629a6`, logo antes do Admin v1)**: `DatasetSidebar.tsx`
ganhou um nível hierárquico acima de tudo — `SidebarServiceGroup`, hoje
só "BigQuery", **deliberadamente preparado pra o Hub expandir pra outros
serviços GCP observáveis** (Cloud Storage, Pub/Sub, Dataflow — ver
Backlog item 14, adiado conscientemente por decisão do usuário em
2026-08-17, mas a estrutura de sidebar já não precisará de retrabalho
quando isso acontecer). "Governança" e "FinOps" eram headers estáticos,
viraram seções recolhíveis de verdade; todas as subseções passaram a
abrir recolhidas por padrão (mudança de comportamento pra "Datasets
disponíveis", que antes abria aberta) — só o grupo "BigQuery" abre por
padrão, por ser o único serviço hoje.

Depois disso, mais um ajuste pequeno em `77dacce` (junto com o Admin
v1.1): "Buscar tabelas" moveu pra dentro de "Datasets disponíveis".

---

## Admin ACL — controle de acesso por usuário × projeto (ADR-009, v1.0→v1.3)

Reconstruído a partir de `docs/adr/ADR-009-acl-usuario-projeto.md` e
`docs/specs/admin.md` v1.3 — trabalho spread pelos PRs #20 e #21, nenhum
registrado em SESSIONLOG até agora. **Nota de inconsistência encontrada
nesta reconstrução:** o ADR-009 tem data "2026-08-18" no cabeçalho e uma
"Nota de extensão" datada "2026-08-20" — mas todos os commits reais desta
feature (`391d159` até `301fc59`) rodaram no mesmo dia, **2026-08-17**
(confirmado via `git log --format=%ad`). As datas do ADR parecem ter sido
assumidas/erradas no momento da escrita em vez de checadas — mesma classe
de erro que a seção "Registro de acessos e configurações" do CLAUDE.md
existe pra evitar, só que em datas de documento, não em concessões de
acesso. Não corrigido nesta sessão (fora do escopo de só atualizar o
SESSIONLOG) — sinalizar ao usuário.

### Motivação
O modelo cross-project (ADR-006) dá à SA de runtime do Hub acesso IAM
simultâneo a vários projetos-cliente. Até aqui o único gate era
`Depends(get_current_user)` — valida a sessão (login OAuth), não se
aquele usuário deveria ver aquele `project_id` específico. Com 5+
projetos-cliente no mesmo Hub, qualquer usuário logado podia digitar o
`project_id` de outro cliente no seletor e ler os dados dele —
vazamento cross-cliente real.

### v1.0 (commit `391d159`) — fundação
Nova coleção Firestore `hub_users/{email}` (`is_admin: bool`,
`allowed_projects: list[str]`, aceita wildcard `"*"`). Duas dependencies
novas em `core/auth.py`: `require_admin` (403 se `!is_admin`) e
`require_project_access` (403 `ProjectNotAuthorizedError` se
`project_id` não estiver na lista do usuário) — a segunda substitui
`get_current_user` como gate em **todo** endpoint que recebe
`project_id` como path param (catalog, freshness, profiling, quality,
lineage, pii, access, finops, projects). **Fail closed por padrão**:
usuário sem documento não acessa projeto nenhum, mesmo com a SA tendo
IAM lá. Tela `/admin` nova, gated por `require_admin`. Decisão
documentada de usar Firestore (não Secret Manager) — a SA já lê/escreve
Firestore (favoritos, histórico), e Secret Manager é versionado/imutável
por natureza, inadequado pra CRUD via UI; foi exatamente o
`@lru_cache` sem TTL de `OAUTH_ALLOWLIST` que causou staleness real
numa sessão anterior — o Firestore aqui é sempre leitura fresca, sem
cache, de propósito.

**Bootstrap do primeiro admin**: `hub_users` vazio bloqueia `/admin`
pra todo mundo (ninguém é admin, ninguém cria o primeiro registro pela
UI) — resolvido com `scripts/seed_admin.py` (credenciais do operador,
não a SA de runtime). Confirmado rodado em `observability-hub-prod`
antes do PR #20 promover o gate pra produção (ver corpo do PR #20).

### v1.1 (commits `6ec0817`, `26a49b1`, `77dacce`) — feedback de uso real
Três adições, motivadas por feedback de uso da v1.0 já em produção:

1. **`hub_projects/{project_id}`** (`is_public: bool`) — eixo
   **independente** de `allowed_projects`: libera um projeto pra
   qualquer usuário, inclusive quem ainda não tem documento em
   `hub_users` (usuário futuro). `has_project_access` checa
   `hub_projects` **antes** de olhar o usuário. Aba "Por projeto" em
   `/admin` é a visão inversa da aba "Por usuário".
2. **`access_requests`** — qualquer usuário autenticado pode pedir
   acesso a uma lista de `project_id` (`POST /api/v1/access-requests`,
   fora do prefixo `/admin` de propósito). Filtra automaticamente
   projetos já acessíveis e pedidos duplicados pendentes. Admin vê/
   aprova/nega em `/admin` → aba "Solicitações", com badge de
   pendentes no ícone de admin (`refetchInterval` 60s, sem WebSocket).
3. **Mensagens de erro visíveis** — `ApiErrorNotice` ganhou uma prop
   `action` (CTA opcional); `ProjectSelector` passou a mostrar
   "Solicitar acesso" quando o erro é de autorização. `26a49b1`: os
   comandos `gcloud` de remediação (que fazem sentido pro admin do
   projeto GCP alvo) passaram a ficar ocultos nesse erro específico via
   `showFix={false}` — usuário comum só vê a mensagem, não o comando
   técnico que não pode nem deveria rodar.

### v1.2 (commit `e29b4ea`) — painel de uso/gestão, 1ª parte
Nova aba "Uso do Hub" em `/admin` (**é daqui que vem o nome da branch
`feature/admin-usage-analytics`**) — três leituras cross-usuário que
agregam dado que já existe em outros domínios, mais uma coleção nova:

- **Logins**: nova coleção `login_events/{auto_id}`, gravada em
  `POST /auth/callback` (best-effort — falha aqui nunca pode impedir o
  login). Antes da v1.2 login era 100% stateless, sem registro nenhum.
  Endpoint devolve buckets diário/semanal/mensal (padrão DAU/WAU/MAU).
- **Favoritos entre usuários**: lê `collection_group("favorites")` sem
  filtro (evita índice manual de collection-group), `owner_email`
  derivado do path do documento-pai — drill-down bidirecional
  (usuário→itens, base→usuários) no mesmo payload achatado.
- **Atividade de profiling**: `quality/history_repository.py::save_run`
  passou a gravar `project_id`/`dataset_id`/`table_id` explícitos
  dentro de cada run (antes só existiam implícitos no ID do
  documento-pai, ambíguo de parsear de volta) — lido via
  `collection_group("runs")`.

### v1.3 (commits `0266edb`, `568622a`, `301fc59`) — mais 3 mapeamentos + UX
Três novas leituras na mesma aba "Uso do Hub":

- **Solicitações de acesso** — zero gravação nova, `access_requests` já
  tinha tudo; agrega por mês (`total`/`approved`/`denied`/`pending`),
  lista projetos mais pedidos, `approval_rate` (`null` quando ainda não
  houve nenhum pedido resolvido, nunca "0%" falso).
- **Navegação agregada** — zero gravação nova, lê `history_table_views`/
  `history_searches` (já existiam, cap de 20/usuário) via
  `collection_group` — front agrega "tabelas mais vistas"/"buscas mais
  frequentes". Cap de 20 é explícito na UI como limitação (métrica
  recente, não histórico completo).
- **Atividade de scans de PII** — **gravação nova**: até aqui PII só
  tinha cache em memória (5min), sem histórico. Novo
  `pii/history_repository.py`, grava em `pii_scan_history/{doc}/scans/
  {auto-id}` a cada execução real (não em cache hit). Nome da
  subcoleção é deliberadamente `scans`, não `runs` — a agregação lê via
  `collection_group("runs"|"scans")`, que ignora o path do
  documento-pai; nomes iguais fariam profiling e PII se misturarem na
  mesma leitura.

`568622a`: refactor que padronizou colunas projeto/dataset/tabela e
filtros nas listas da aba "Uso do Hub" (as 6 seções tinham crescido
cada uma com sua própria tabela ad-hoc). `301fc59`: tópicos recolhíveis
+ paginação nas listas — a aba tinha ficado longa demais com 6 seções
de analytics simultâneas.

---

## Documentação para cliente — playbooks e manuais (PRs #22, #23, #24)

Três commits, todos **docs-only** (não tocam `apps/`, então não
disparam deploy — confirmado via `gh run list`, nenhum "Deploy" job
rodou pra esses três pushes). Continuam na mesma branch
`feature/admin-usage-analytics` por não terem justificado uma branch
nova. Todos os quatro documentos citam `docs/onboarding-cliente.md`
e/ou os ADRs 006/009 como referência técnica de fundo — são a camada
"roteiro de execução rápida"/"material voltado a cliente final" em
cima da mesma base já existente.

### `docs/playbooks/liberar-projeto-para-o-hub.md` (commit `181aeef`, 216 linhas)
Playbook interno: "eu já tenho um projeto GCP com dados — o que preciso
fazer pra deixar o Hub ler esse projeto?". Explicitamente **não** é
fonte de verdade — aponta pra `docs/onboarding-cliente.md` pra isso, e
pede que quem executar o playbook volte lá pra registrar a linha
concedida (mesmo processo de sempre). Deixa claro que liberar a nível
de infraestrutura GCP é só metade do caminho — a segunda camada (ACL do
Hub, ADR-009) é liberada depois, dentro do próprio `/admin`.

### `docs/playbooks/hospedar-hub-em-novo-projeto.md` (commit `181aeef`, 449 linhas)
Playbook interno: "quero rodar minha própria cópia do Hub (hospedagem e
administração) em projetos GCP diferentes dos originais — o que precisa
ser feito do zero?". Bootstrap único por par de ambientes (dev/prod);
depois de concluído, o dia a dia vira só `git push`. Cobre os 2 Cloud
Run, 1 Artifact Registry compartilhado, SAs de runtime, Firestore,
Secret Manager, WIF e bucket GCS de state — o inventário completo de
infraestrutura que o Hub precisa pra existir.

### `docs/manual-implementacao-cliente.md` (commit `0e2acbe`, 361 linhas)
Primeiro documento **voltado a cliente final** (linguagem sem jargão
interno) — implementação de uma instância própria do Hub no GCP do
cliente, hospedagem/administração completas sob controle dele. Seção
explícita "Segurança e escopo" (o que o processo faz e não faz): tudo
dentro dos projetos do próprio cliente, sem credencial de longa duração
(WIF), permissões mínimas restritas aos dois projetos criados,
reversível (apagar os projetos remove tudo), nada trafega pra fora do
ambiente GCP do cliente, auditável via Terraform. Público: responsável
técnico com papel *Owner* no GCP.

### `docs/manual-liberacao-acesso-cliente.md` (commit `0461b36`, 197 linhas)
Segundo documento voltado a cliente final — a contraparte do playbook
`liberar-projeto-para-o-hub.md`, mas em linguagem de cliente: como
autorizar o Hub (já hospedado, seja pelo time do Hub ou pelo próprio
cliente via o manual acima) a ler um projeto GCP existente. Mesma
seção "o que faz/não faz": só leitura, nada instalado no projeto do
cliente, acesso escopado a uma SA nomeada, revogável a qualquer
momento, cliente confirma cada permissão antes de conceder (comandos
explícitos, nada automático). Público: responsável técnico com role
*Owner*/*IAM Admin*. Tempo estimado 10–15min (vs. meio dia do manual de
implementação).

---

## Sprint 3.1 — Auth (Google OAuth) + UX pessoal (concluída, PR #17)

Sessão anterior a esta, reconstruída a partir da descrição do PR #17
(`gh pr view 17`) — o SESSIONLOG não foi atualizado entre o encerramento
da Sprint 2.2/2.3 e o início desta sessão (falha de processo já
sinalizada ao usuário nesta sessão).

- **Auth**: senha hardcoded (`AuthGate`, dívida técnica registrada no
  backlog da Sprint 2) removida por completo, substituída por Google
  OAuth 2.0 de verdade — `domains/auth/` (`/login`, `/callback`, `/me`,
  `/logout`), JWT de sessão de 12h em cookie `httpOnly; Secure;
  SameSite=None`, allowlist por domínio/email lida do Secret Manager.
  Todos os routers de dados (catalog, freshness, profiling, projects)
  passaram a exigir sessão válida no backend, não só proteção de rota no
  frontend. Dois fixes pós-validação: cookie de logout não limpava de
  verdade (`delete_cookie` do Starlette não replicava os atributos do
  cookie original), redirect pro `/login` não era imediato.
- **Modal de profiling**: bug de colapso do schema corrigido em dois
  níveis (colunas STRUCT/ARRAY colapsáveis individualmente + seção
  inteira), fix de scroll horizontal vazando dos controles pra fora do
  modal, refatorado pra Tabs (shadcn/ui) — "Schema" e "Análise de
  qualidade" como abas separadas.
- **Favoritos**: `domains/favorites/`, Firestore por usuário
  (`users/{email}/favorites/{doc_id}`, doc_id determinístico), estrela em
  cada linha de `AssetsTable` com toggle otimista, seção "Favoritos" na
  sidebar com navegação + highlight.
- **Histórico** (de navegação — diferente do "histórico de qualidade" da
  Sprint 3.2): `domains/history/`, duas subcoleções por usuário
  (`history_table_views`/`history_searches`, decisão pra evitar depender
  de índice composto não provisionado), seção "Recentes" na sidebar,
  dropdown de buscas recentes na tela de busca.
- 269 testes backend, `ruff`/`biome`/`tsc`/`vite build` limpos. Validado
  em dev pelo usuário (login/logout, allowlist, as 4 melhorias do modal,
  favoritos e histórico); renderização visual não verificada por este
  assistente em nenhum momento (mesma limitação de Chromium headless de
  sempre).

---

## Sprint 2.2 — Funcionalidade 1 (metadados de partição)

**Versão 1 (revertida pelo usuário):** `get_partition_stats()` consultava
`INFORMATION_SCHEMA.PARTITIONS` (dataset-qualified, metadado gratuito),
retornando N/D direto para datasets multi-região (US/EU) sem tentar a
query. Como todos os datasets de dev/prod estão em `US`, isso significava
N/D sempre — comportamento tecnicamente correto pra limitação do BQ, mas
inútil na prática. PR #14 foi aberto com essa versão e fechado pelo
usuário sem merge por estar incorreto.

**Versão 2 (atual):** `get_partition_stats()` roda uma query real e leve
(uma coluna só, sem filtro) direto na tabela:
```sql
SELECT MIN(`{campo}`) AS min_partition, MAX(`{campo}`) AS max_partition,
       COUNT(DISTINCT `{campo}`) AS partition_count
FROM `{project}.{dataset}.{tabela}`
```
Funciona em qualquer região (não depende de `INFORMATION_SCHEMA.
PARTITIONS`), mas tem custo real de bytes escaneados (ao contrário de
metadado do `INFORMATION_SCHEMA`) — por isso ganhou cache TTL de 5min por
tabela (`repository._partition_stats_cache`, mesmo padrão do
`get_table_cached` de `core/bigquery.py`, mas local ao domínio catalog).
`campo` vem de `partition_column` (já derivado de
`COLUMNS.is_partitioning_column`, funciona em qualquer região). Também
ganhou `partition_type` ("event_date (DAY)"), lido de
`bq_table.time_partitioning`/`range_partitioning` — já vinha no
`client.get_table()` cacheado que `get_tables_summary` já chamava pra
row_count/size/modified, sem chamada extra.

**Confirmado ao vivo em dev** (`observability-hub-dev`, branch
`feature/partition-metadata`, commit `ea31bd6`):

| Tabela | Partitioned | Tipo | Min | Max | Count |
|---|---|---|---|---|---|
| `RAW.events` | true | `event_date (DAY)` | `2021-01-01` | `2021-01-30` | `3` |
| `TRUSTED.ga4_events` | true | `event_date (DAY)` | `2021-01-01` | `2021-01-18` | `4` |
| `TRUSTED.sessions` | true | `session_date (DAY)` | `2021-01-06` | `2021-01-31` | `7` |
| `RAW.crm_leads` | false | — | — | — | — |

Valores reais (dados mock de dev estão em jan/2021), não N/D — objetivo da
correção alcançado. `RAW.crm_leads` (não particionada) corretamente sem
dados de partição.

**Não verificado visualmente:** renderização real da tabela no frontend —
Chromium headless não roda neste sandbox (limitação já registrada em
sessões anteriores, ver "Decisões e erros de sessões anteriores" #7).
Validado só via `tsc`/`vite build`/`biome check` limpos e a API real via
`curl`.

Além dos 3 campos, ganhou também `partition_type` na tabela de ativos e um
botão **"Ver partições"** (linhas particionadas) que abre um modal com a
lista completa de partições distintas + contagem de linhas — novo
endpoint `GET /api/v1/catalog/{project_id}/datasets/{dataset_id}/
tables/{table_id}/partitions` (`TableNotPartitionedError` → 400 pra tabela
não particionada). Testado ao vivo em `RAW.events`: 3 partições, ordem
decrescente, valores batendo com a query direta. Commit `a0696fb`.

---

## Sprint 2.2 — Funcionalidade 2 (botão de refresh)

Só frontend. `RefreshButton` (`src/components/RefreshButton.tsx`,
`RotateCcw` do lucide, `animate-spin` + `disabled` durante fetch) nos
headers de `CatalogDatasetPage` (refetch de tables/datasets/freshness — as
três alimentam a página) e `FreshnessPage` (refetch de freshness). Não
entrou em `CatalogOverviewPage` (placeholder sem dados, dataset ainda não
selecionado) nem no modal de profiling, como pedido. Commit `a4083fc`.
Validado pelo usuário em dev (comportamento visual — spin/disable/reload
— não pôde ser confirmado neste sandbox, ver limitação de Chromium
headless acima).

---

## Sprint 2.2 — Funcionalidade 3 (busca reversa tabela → datasets)

Novo endpoint `GET /api/v1/catalog/{project_id}/search?q=&mode=exact|
contains` — busca em `INFORMATION_SCHEMA.TABLES` de todas as regiões do
projeto em paralelo (`repository.search_tables`, mesma técnica de
`discover_regions`). Resultado agrupado em `datasets_with_match` (com
`last_modified_time` real via `client.get_table()`, reaproveitando
`core.bigquery.get_tables_metadata`) e `datasets_without_match`.

`datasets_without_match` **não** lista todo dataset do projeto sem a
tabela — só os que têm outra tabela da mesma série: prefixo derivado
removendo o sufixo numérico final de `q` (`repository.
derive_search_prefix`, ex: `"events_20260812"` → `"events_"`), buscado via
`GROUP BY` + `MAX(table_name)` por dataset. Sem sufixo numérico em `q`,
`datasets_without_match` fica vazio — não há "série" pra comparar.

Frontend: nova seção "Busca" na sidebar (ícone `Search`), campo + toggle
Exato/Contém (dois `Button`, sem novo componente shadcn), busca como
`useMutation` (não `useQuery` — é sob demanda, não reativa), mensagem de
loading, dois grupos de resultado (✅ encontrado / ❌ ausente com motivo) e
mensagem de vazio pra `contains` sem resultado. Commit `50526e9`.

**Confirmado ao vivo em dev** (`observability-hub-dev`) — importante: os
dados mock mudaram desde a spec original da Sprint 2.2 (que previa "RAW
como único dataset com match"). Dev agora tem 3 datasets
`analytics_100001/2/3`, cada um com tabelas `events_YYYYMMDD` sharded por
nome (cenário GA4 real, não só `RAW.events` particionado por coluna):

| Busca | Resultado |
|---|---|
| `q=events_20260812&mode=exact` | 3 matches (`analytics_100001/2/3`) |
| `q=events_20260813&mode=exact` (data ainda não carregada) | 0 matches, 3 `datasets_without_match` com `reason=prefix_exists` e `latest_partition=events_20260812` — cenário exato da spec |
| `q=crm&mode=contains` | 1 match (`RAW.crm_leads`) |
| `q=zzz_nao_existe&mode=contains` | Vazio, `200 OK` |

`RAW.events` nunca aparece nessas buscas — é uma tabela só, particionada
por coluna (`event_date`), não por nome sharded, então não bate com busca
por nome de tabela. Validado pelo usuário.

---

## Sprint 2.3 — 4 melhorias de UX (commit `2630fb9`)

Implementadas em um único commit (a Sprint 2.3, diferente da 2.2, não
pediu branch/commit por item — só documentação separada, ver abaixo).
Todas testadas em dev e validadas pelo usuário.

1. **Sidebar sem bolinhas de status SLA**: `DatasetSidebar.tsx` não busca
   mais `useProjectFreshness` nem renderiza `STATUS_DOT_COLOR` — só nome +
   contagem de tabelas/views. O backlog item "datasets só com views sem
   indicador de freshness na sidebar" (ver "Backlog" abaixo) fica
   obsoleto — não há mais indicador nenhum ali.

2. **Projeto persistido em localStorage**: `hooks/useLastProject.ts` já
   tinha `setLastProjectId` (escrita) mas nenhuma leitura — ganhou
   `getLastProjectId`/`clearLastProjectId`. `ProjectSelector.tsx` restaura
   e revalida automaticamente no mount; se a revalidação falhar, limpa o
   storage e volta pro campo vazio (só no caminho de restore automático —
   uma falha de validação manual, digitada pelo usuário, continua
   deixando o campo preenchido pra ele corrigir, comportamento inalterado
   nesse caso).

3. **Mode `not_contains` na busca**: `SearchMode` ganhou o terceiro valor.
   `service._search_not_contains` trata à parte — não é uma variação da
   query SQL de match dos outros modes, é uma pergunta invertida (usa
   `get_datasets_summary` pra saber todos os datasets do projeto e
   `search_tables(mode="contains")` pra saber quem tem match; a diferença
   vira o resultado). `datasets_with_match` fica sempre vazio nesse mode.

4. **Resultado da busca em tabela ordenável/filtrável**: dois componentes
   novos (`SearchMatchesTable`, `SearchAbsentTable`) com sort client-side
   por coluna e filtro de texto em Dataset/Tabela. A coluna "Linhas"
   pedida na spec não existia no backend (`GET /search` nunca retornou
   `row_count`) e a spec dizia "sem mudança de backend" — conflito real,
   perguntado ao usuário, que escolheu adicionar `row_count` ao backend
   (reaproveita a mesma chamada `client.get_table()` já feita pra
   `last_modified_time`, sem query BQ extra).

**Confirmado ao vivo em dev** (via `curl`, backend):
- `mode=not_contains&q=crm`: exclui corretamente `RAW` (único dataset com
  `crm_leads`), lista os outros 5 datasets com `reason=no_match`.
- `mode=exact&q=events_20260812`: `row_count: 1000` real em cada match.
- `GET /projects/.../validate` seguiu funcionando (regressão check pro
  fluxo de restore do item 2).

**Não verificado visualmente**: renderização real das 4 melhorias no
browser — mesma limitação de Chromium headless de sempre. Validação
visual de todas as 7 funcionalidades desta sessão (2.2 + 2.3) foi feita
pelo usuário, não por este assistente.

---

## Sprint 2.2/2.3 — Documentação

Atualizados nesta sessão, depois das 7 funcionalidades validadas em dev
(commit separado da Sprint 2.3, como pedido):
- `CHANGELOG.md`: nova seção "Sprint 2.2 e 2.3" com o que foi feito, os 2
  erros/aprendizados da sessão (reversão da estratégia de partições;
  conflito "Linhas sem mudar backend") e tabela de próximas fases
  atualizada (Fase 2D e Sprint 2.2/2.3 marcadas concluídas, Fase 3 como
  próxima).
- `docs/prd.md`: tabela de roadmap (seção 7) atualizada — Fase 1 e Fase 2
  estavam desatualizadas (marcadas "em andamento"/"pendente" mesmo já
  concluídas antes desta sessão).
- `docs/adr/ADR-008-terraform-plan-prod-removido.md`: novo ADR
  documentando por que `terraform-plan.yml` não tem job "Plan (prod)" —
  decisão já estava implementada (o workflow já tinha um comentário
  explicando) mas nunca formalizada em ADR. Contexto → decisão →
  alternativas → consequências, como as demais.
- `docs/specs/catalog.md` (v1.4 → v1.5): endpoints `/partitions` e
  `/search` documentados, incluindo a ressalva de que `get_partition_stats`
  não é mais metadado gratuito (é query real, ao contrário do resto da
  spec) — e por quê (`INFORMATION_SCHEMA.PARTITIONS` não serve como fonte
  única quando 100% do ambiente observado é multi-região).
- `docs/specs/profiling.md` (v1.1 → v1.2): suporte a views (omissão de
  `TABLESAMPLE`), schema preview no modal (STRUCT/ARRAY com badge
  "Complexo" mas visível no schema, mesmo sem métricas), e a tabela de
  tipo lógico inferido corrigida pra refletir a ordem real de checagem
  (tipo físico antes de heurísticas de cardinalidade — a ordem antiga era
  auto-contraditória).
- `SESSIONLOG.md`: este arquivo, nesta seção.

---

## O que foi feito na Sprint 2

A Sprint 2 cobriu do PR #2 ao #13 (o PR #1, deploy do frontend no Cloud Run,
já estava documentado no encerramento da sessão anterior). Trabalho spread
por várias sessões — o que segue é a reconstrução a partir do histórico real
de PRs (`gh pr list`/`gh pr view`), não só da sessão mais recente.

### Infra e correções de plataforma
- **PR #2 — CORS para a segunda URL do Cloud Run**: todo serviço Cloud Run
  responde em duas URLs válidas (a com hash e a legada por número de
  projeto); só a primeira estava na allowlist de CORS do backend, quebrando
  o frontend quando acessado pela URL de project number. Módulo `cloud-run`
  ganhou `output "service_url_alt"` (via `data "google_project"`,
  reaproveitável), e as duas URLs entraram em `OBSERVABILITY_HUB_CORS_ORIGINS`
  nos dois ambientes.
- **PR #10 / #11 — bumps de versão pra forçar redeploy em dev**: dev tinha
  ficado defasado de `main` (deploy automático só dispara em push que toca
  os paths do workflow, não em "está tudo commitado" — mesma armadilha já
  registrada na sessão anterior). Bump de versão em `package.json` (frontend)
  e `pyproject.toml`/`uv.lock` (backend) sincronizou dev com o código real.

### Domínio quality/profiling
- **PR #3 — 403 limpo em vez de 500 no profiling**: a runtime SA tinha
  `metadataViewer`+`jobUser` (suficiente pra catalog/freshness, só
  `INFORMATION_SCHEMA`), mas profiling roda SQL real contra dados de tabela
  e precisa de `bigquery.dataViewer` — faltava nos dois ambientes. As 4
  funções de query em `domains/quality/repository.py` passaram a capturar
  `Forbidden` e relançar `ProjectAccessDeniedError` (já mapeada pra 403 no
  handler). O handler em `main.py` também estava sugerindo só uma role no
  `fix`; passou a sugerir as três (idempotente, seguro rodar mesmo quando só
  uma faltava).
- **PR #4, #5, #6 — três rodadas até acertar o modal de profiling**: scroll
  (modal + área de SQL), depois largura/KPIs/SQL colapsável, depois a causa
  raiz real da largura: `DialogContent` do shadcn já vem com `sm:max-w-sm`
  embutido, e no CSS compilado pelo Tailwind v4 essa regra `sm:` aparece
  **depois** de qualquer `max-w-[...]` simples adicionado via `className` —
  vencia o empate de especificidade silenciosamente em qualquer tela
  ≥640px, apesar do build passar limpo nas duas tentativas anteriores.
  Resolvido com `w-[90vw]! max-w-[1000px]!` (sintaxe `!important` do
  Tailwind v4), confirmado inspecionando o CSS gerado.
- **PR #8 — profiling em views**: `TABLESAMPLE SYSTEM` não é suportado pelo
  BigQuery em VIEW/MATERIALIZED VIEW — causava "Failed to fetch". Query
  builder ganhou `is_view: bool` (omite `TABLESAMPLE`/`sample_percent`
  quando `True`), detectado via `INFORMATION_SCHEMA.TABLES`. Frontend
  desabilita o campo de amostragem com aviso quando a tabela é view. Mesmo
  PR separou a contagem de tabelas e views no catálogo (sidebar e KPI
  cards), que antes vinham somadas sob um único rótulo "tabelas".
- **PR #9 — schema da tabela no modal antes de rodar profiling**: nova
  `SchemaTable` (Nome/Tipo/Nullable) usando o endpoint de detalhe já
  existente, com parsing de subcampos STRUCT/ARRAY (badge "Complexo"),
  destaque pra colunas de data e badge de coluna de partição. Header do
  modal ganhou badges "Particionada por"/"Clusterizada por".
- **PR #7 — inferência de tipo lógico**: colunas numéricas (INTEGER,
  FLOAT64, NUMERIC, BIGNUMERIC, INT64) e de data/hora (DATE/DATETIME/
  TIMESTAMP) passaram a ter `inferred_logical_type` correto direto pelo tipo
  físico, sem cair nas heurísticas de cardinalidade (categorical/id) que
  valiam só quando o tipo físico não decidia sozinho.

### Domínio freshness
- Colunas de contagem por SLA na tabela de freshness (commit `8324fbe`,
  direto em `main`, sem PR associado).
- Backlog registrado (commit `ab68237`, também direto em `main`): datasets
  só com views não têm indicador de freshness na sidebar (sem
  `modified_time` de dados) — ainda pendente, ver "Backlog" abaixo.
- **Esta sessão (PR #12)**: `get_tables_summary` (catalog) e
  `get_table_freshness` (freshness) passaram de `INFORMATION_SCHEMA.
  TABLE_STORAGE` (lag de até 24h) para `client.get_table()` — tempo real,
  chamadas em paralelo (`ThreadPoolExecutor`) com cache TTL de 5min
  compartilhado (`core/bigquery.py`). Escopo decidido com o usuário: as
  visões agregadas por projeto (`get_datasets_summary`,
  `get_freshness_summary_by_dataset`) ficaram em `TABLE_STORAGE` de
  propósito, pra não virar uma chamada de API por tabela do projeto inteiro
  numa tela de dashboard. Specs `catalog.md` (v1.3) e `freshness.md` (v1.2)
  atualizadas.

### UX geral e autenticação
- **PR #7 — 5 melhorias de UX**: tabela de resultados sem scroll horizontal
  (truncamento com ellipsis em Min/Max), seletor de projeto migrado da tela
  `/` isolada pra `Topbar` (visível em qualquer página, `ProjectContext` +
  `ProjectSelector`, rotas perderam o prefixo `/p/:projectId`), e
  `AuthGate` — tela de login com senha hardcoded (`senha123`) e sessão em
  `sessionStorage`. Ver nota de dívida técnica no Backlog.
- **Esta sessão (PR #13)**: `GET /projects/{id}/validate` ganhou
  `is_native` (compara `project_id` com `client.project`, mesma fonte já
  usada no fix do 403). Badge na topbar — verde "Projeto nativo" / amarelo
  "Projeto externo" — com tooltip. Spec `catalog.md` bump pra v1.4.

### IAM cross-project (esta sessão, fora de qualquer PR — aplicado via `gcloud` direto)
O usuário rodou manualmente (com aprovação explícita a cada comando, via
`!`) bindings cruzados entre os dois projetos:
- `backend-run@observability-hub-prod` ganhou `metadataViewer` +
  `jobUser` + `dataViewer` em `observability-hub-dev`.
- `backend-run@observability-hub-dev` ganhou as mesmas três roles em
  `observability-hub-prod`.

Ambas as direções foram confirmadas como **intencionais** pelo usuário
depois de eu (assistant) sinalizar o trade-off de segurança: dev faz deploy
automático em qualquer push sem gate de revisão, então a SA de dev agora
consegue ler dados reais de prod (potencialmente com PII, dado o escopo do
produto) a partir de qualquer branch nova. Ver "Backlog" — considerar
revisitar se o risco incomodar mais adiante.

---

## Erros encontrados e resolvidos (Sprint 2)

- **500 em vez de 403 no profiling**: `Forbidden` do BigQuery vazando sem
  tratamento — corrigido capturando e relançando `ProjectAccessDeniedError`
  (PR #3).
- **CORS quebrando só na URL alternativa do Cloud Run**: cada serviço
  responde em duas URLs válidas simultâneas, só uma estava na allowlist
  (PR #2).
- **`TABLESAMPLE SYSTEM` não suportado em views**: profiling de view dava
  "Failed to fetch" — query builder passou a omitir `TABLESAMPLE` quando
  `is_view=True` (PR #8).
- **`sm:max-w-sm` do shadcn vencendo `max-w-[...]` customizado**: duas
  rodadas (PR #4, #5) pareceram corrigir a largura do modal de profiling
  sem resolver de fato — causa raiz só foi achada na terceira (PR #6),
  inspecionando o CSS compilado: a ordem das regras no stylesheet gerado
  pelo Tailwind v4, não a ordem no `className`, decide o empate de
  especificidade. Resolvido com `!important` explícito.
- **Dev ficando defasado de `main` silenciosamente**: deploy automático só
  dispara em push que toca os paths do workflow — commits direto em `main`
  (ou merge de branch cortada de um ponto antigo) não disparam redeploy de
  dev. Aconteceu de novo nesta sprint (PR #10/#11), mesma causa já registrada
  no encerramento da sessão anterior. Ainda não virou automação — continua
  sendo descoberto manualmente comparando a tag da imagem rodando contra
  `git log`.
- **Binding de IAM cruzado aplicado sem intenção clara**: nesta sessão, o
  usuário rodou um `add-iam-policy-binding` que dava à SA de prod acesso ao
  BigQuery de dev — comando idêntico ao exemplo estático hardcoded na spec
  `catalog.md` (SA de prod, uma role só), não ao `fix` real que a API
  retornaria (três roles, SA do ambiente que fez a chamada). Esclarecido
  com o usuário, que confirmou a intenção real (Hub observando o outro
  ambiente como projeto-alvo) e pediu pra completar com as roles que
  faltavam nas duas direções.
- **Prod achado com 0 datasets nas sessões anteriores, agora com 3**:
  verificado ao vivo nesta sessão (`GET /projects/observability-hub-prod/
  validate` → `total_datasets: 3`) — a suposição antiga ("0 é esperado, sem
  mock em prod") não é mais verdade. Não investigado a fundo — só uma
  correção de estado registrada aqui pra não repropagar a suposição velha.

---

## Decisões e erros de sessões anteriores (ainda válidos)

1. `INFORMATION_SCHEMA.TABLE_PARTITIONS` não existe em multi-região US/EU e
   não tem o *nome* da coluna de particionamento — usar
   `COLUMNS.is_partitioning_column`.
2. `TABLE_STORAGE.storage_last_modified_time` é o campo correto (não
   `last_modified_time`, `modified_time` nem `last_altered`) — mas ver PR
   #12 acima: catalog/freshness por tabela não usam mais `TABLE_STORAGE`,
   só as visões agregadas por projeto ainda dependem disso.
3. `COLUMN_FIELD_PATHS` é a fonte de `description` de colunas, não `COLUMNS`.
4. `SelectValue` do shadcn/base-ui precisa de render-prop explícito pro
   label — não deriva automaticamente dos `SelectItem` filhos.
5. Antes de qualquer afirmação sobre configuração do BigQuery neste projeto,
   validar ao vivo contra `observability-hub-dev` (ou, quando relevante,
   `observability-hub-prod` — ver erro do "0 datasets" acima).
6. Comandos `gcloud ... add-iam-policy-binding` (e outras mudanças de IAM)
   são bloqueados pelo classificador de auto mode quando o assistant tenta
   rodá-los — sempre passar o comando pronto pro usuário rodar via `!`, um
   comando por vez (colar dois comandos com `!` no mesmo bloco só aplica o
   prefixo no primeiro).
7. Chromium headless não roda neste sandbox (falta `libnspr4.so`, sem
   `sudo` disponível) — recorrente em várias sessões (PR #6, #7, #8, #9,
   #13). Verificação de UI fica limitada a: `tsc`/`vite build`, `biome
   check`, inspeção do CSS/bundle compilado, e teste da API real que o
   componente consome. Sempre declarar explicitamente essa limitação em vez
   de alegar verificação visual que não aconteceu.

---

## Estado da infraestrutura

```
GCP Dev  (observability-hub-dev)
├── Cloud Run: backend ✅ tag 9bafbee (feat/storage-mvp — domínio storage
│   completo, deploy automático verde a cada push desta sessão)
├── Cloud Run: frontend ✅ tag 9bafbee, idem
├── Artifact Registry: apps ✅ (compartilhado backend+frontend)
├── IAM backend-run@...-dev: metadataViewer + jobUser + dataViewer +
│   logging.viewer + logging.privateLogViewer no próprio projeto e em
│   observability-hub-prod (cross-project completo nas 5 roles de
│   BigQuery/Logging, sem mudança nesta sessão)
├── IAM storage.bucketViewer + storage.objectViewer: **cross-project
│   completo nos dois projetos** (backend-run@...-dev e
│   backend-run@...-prod, cada um com as duas roles no próprio projeto
│   e no outro — matriz 2×2 confirmada ao vivo via `gcloud projects
│   get-iam-policy` em 2026-08-18)
├── Data Access audit logs: bigquery.googleapis.com (DATA_READ,
│   DATA_WRITE, ADMIN_READ) em dev e prod, sem mudança. storage.
│   googleapis.com (DATA_READ) — **habilitado em dev E prod** nesta
│   sessão (prod foi decisão consciente do usuário, ciente da nota de
│   volume da spec seção 6.2)
├── Checklist completo de IAM/API/audit config pra onboarding de projeto
│   alvo vive em docs/onboarding-cliente.md — registro de concessões
│   está em dia até 2026-08-18 (inclui as duas roles de storage nos
│   dois projetos e os dois audit configs novos)
├── Firestore (Native mode): sem mudança nesta sessão (domínio storage
│   não usa Firestore — tudo vem de GCS/Cloud Logging direto)
├── Pipeline: 597 testes unitários backend, 100% passando, ruff limpo;
│   frontend tsc/biome/vite build limpos; deploy automático verde a cada
│   push (gh run list confirmado até 2026-08-18)
├── Buckets mock: observability-hub-dev-landing (STANDARD, com lifecycle
│   rule), observability-hub-dev-processed (NEARLINE, sem regra),
│   observability-hub-dev-archive (COLDLINE, sem regra, vazio) — já
│   existiam antes desta sessão, usados como fixture real de validação
├── 1 job LOAD real (landing → RAW.crm_leads_staging) e 1 job EXTRACT
│   real (RAW.crm_leads_staging → processed) — já existiam, usados pra
│   validar lineage com bucket
└── Datasets mock: RAW (4 tabelas agora, incluindo crm_leads_staging),
    TRUSTED (2 tabelas), REFINED (1 view)

GCP Prod (observability-hub-prod)
├── Cloud Run: backend ✅ tag c893c60 (merge commit do PR #21 — ainda a
│   última mudança de APP; domínio storage não mergeado em main ainda,
│   só a infra/mocks/IAM já foram promovidos, ver abaixo)
├── Cloud Run: frontend ✅ tag c893c60, idem
├── Artifact Registry: apps ✅ (compartilhado backend+frontend)
├── IAM BigQuery/Logging: simétrico com dev, sem lacunas conhecidas
├── IAM storage.bucketViewer + storage.objectViewer: **promovido nesta
│   sessão** — self (backend-run@...-prod no próprio projeto) e cross
│   (backend-run@...-dev também em prod) — ver bloco de dev acima, é a
│   mesma matriz 2×2
├── storage.googleapis.com: já habilitada antes desta sessão (dependência
│   de outra coisa, não documentado quando)
├── Data Access audit log DATA_READ de storage.googleapis.com:
│   **habilitado nesta sessão** — decisão do usuário, ciente da nota de
│   volume da spec (seção 6.2); confirmado coexistindo com o auditConfig
│   de bigquery.googleapis.com, sem sobrescrever nada
├── Buckets: observability-hub-prod-landing (STANDARD + lifecycle rule
│   idêntica à de dev), -processed (NEARLINE), -archive (COLDLINE) —
│   criados nesta sessão, espelhando dev
├── 1 objeto mock em landing + 1 job LOAD real (→ RAW.crm_leads_staging,
│   tabela nova) + 1 job EXTRACT real (→ processed) — criados nesta
│   sessão, mesmo processo de dev
├── Admin ACL gateando 9 routers desde o PR #20, sem mudança
├── total_datasets: 4 (RAW ganhou crm_leads_staging nesta sessão, além
│   do crm_leads que já existia)
└── WIF: attribute_condition restrito a refs/heads/main — plan de prod
    continua revisão manual

GitHub Secrets
├── WIF_PROVIDER_DEV ✅
├── WIF_SA_DEV ✅
├── WIF_PROVIDER_PROD ✅
└── WIF_SA_PROD ✅

`main`/prod: PR #25 mergeado (`d022061`), domínio storage completo em
produção, deploy automático confirmado verde. Branch `feat/storage-mvp`
já mergeada, pode ser deletada quando conveniente.

Working tree limpo — a mudança não commitada em `variables.tf`
(`max_instance_count`) registrada na atualização anterior foi descartada
nesta sessão (`git restore`, sem justificativa encontrada).

**Achado e corrigido no fim desta sessão (investigação de billing, não
relacionado ao domínio storage)**: os 4 serviços Cloud Run (dev/prod ×
backend/frontend) estavam com `run.googleapis.com/cpu-throttling: false`
("CPU sempre alocada", cobra pelo tempo de vida da instância inteira,
não só durante o processamento da requisição) — confirmado que não vem
do Terraform (`resources.cpu_idle` não é declarado no módulo
`cloud-run`) nem do workflow de deploy (`gcloud run deploy` sem essa
flag em nenhum dos 4 workflows), foi mudado manualmente em algum
momento fora do fluxo do projeto. Revertido pros 4 serviços via
`gcloud run services update --cpu-throttling` (volta pro padrão, CPU só
durante request) em 2026-08-18 — confirmado `cpu-throttling: true` nos
4 e health check 200 nos 4 depois do rollout. `min_instance_count = 0`
(scale-to-zero) confirmado intacto nos 4, nunca foi o problema.
```

---

## PRs mergeados na Sprint 2

| PR | Branch | Resumo |
|---|---|---|
| #2 | `fix/cors-frontend-alt-url` | CORS pra segunda URL do Cloud Run |
| #3 | `fix/profiling-forbidden-403` | 403 limpo no profiling (Forbidden → ProjectAccessDeniedError) |
| #4 | `fix/profiling-modal-scroll` | Scroll no modal de profiling e na área de SQL |
| #5 | `fix/profiling-modal-layout` | Modal mais largo, SQL colapsável, KPIs com card |
| #6 | `fix/profiling-modal-layout-v2` | Largura real do modal (causa raiz: especificidade do Tailwind v4) |
| #7 | `fix/ux-improvements` | Tabela sem scroll, tipos lógicos, seletor de projeto na topbar, login |
| #8 | `fix/profiling-view-support` | Profiling em views, contagem separada tabelas/views |
| #9 | `feat/profiling-schema-preview` | Schema da tabela no modal antes de estimar/executar |
| #10 | `chore/frontend-dev-redeploy` | Bump de versão pra forçar redeploy em dev |
| #11 | `chore/backend-dev-redeploy` | Bump de versão pra forçar redeploy em dev |
| #12 | `feat/realtime-metadata` | `client.get_table()` pra volumetria/freshness por tabela (esta sessão) |
| #13 | `feature/native-project-badge` | Badge nativo/externo na topbar (esta sessão) |

(PR #1, deploy do frontend no Cloud Run, foi mergeado na sessão anterior e
já estava documentado no encerramento daquela sessão.)

---

## PRs mergeados depois da Sprint 2

| PR | Branch | Resumo |
|---|---|---|
| #16 | `feature/partition-metadata` | Sprint 2.2 + 2.3 completas |
| #17 | `feat/sprint-3.1` | Auth Google OAuth, favoritos, histórico, fixes no modal de profiling |
| #18 | `feat/sprint-3.2` | Sprint 3.2 completa (7/7): lineage multi-hop, PII, mapa de acesso |
| #19 | `feat/finops-waste-scanner` | FinOps 1/3 — scanner de desperdício (tabelas sem uso, candidatas a partição) |
| #20 | `feat/finops-budget` | FinOps 2/3 (budget) + Admin ACL v1.0/v1.1 + 4 ajustes de UX — **promoveu dev→prod** (39 commits) |
| #21 | `feature/admin-usage-analytics` | Admin ACL v1.2 + v1.3 (painel "Uso do Hub") + refactor de colunas + recolhível/paginação |
| #22 | `feature/admin-usage-analytics` | Docs — playbooks operacionais (liberar projeto, hospedar o Hub) |
| #23 | `feature/admin-usage-analytics` | Docs — manual de implementação pra cliente |
| #24 | `feature/admin-usage-analytics` | Docs — manual de liberação de acesso pra cliente |

Todos os PRs acima (#18–#24) estão **mergeados em `main`/`origin`**,
confirmado via `gh pr list --state all` e `git log origin/main`.

**`feat/storage-mvp` (esta sessão, commits `02adc81`..`ec0ae14`) ainda
não tem PR aberto** — aguardando o checklist de promoção pra prod (ver
seção "Storage — domínio novo"), como pedido explicitamente pelo usuário.

---

## Backlog / dívida técnica identificada

```
Bloqueantes de nenhuma fase, considerar quando aparecer necessidade:

1. ~~Datasets com apenas views não exibem indicador de freshness na
   sidebar~~ — **obsoleto**: Sprint 2.3 removeu os indicadores de status
   SLA da sidebar por completo (pedido do usuário, não relacionado a este
   item). Não há mais bolinha de nenhum tipo ali.

2. Formalizar IAM (bigquery.metadataViewer/jobUser/dataViewer/logging.*,
   incluindo os bindings cross-project) em Terraform em vez de gcloud
   manual — cada vez mais urgente: agora são 5 roles de BigQuery/Logging
   x 2 SAs em dev, mais (depois da promoção de storage pra prod) 2 roles
   de storage x 2 SAs x 2 projetos. Fica mais fácil de perder rastro sem
   IaC a cada domínio novo que precisa de role própria.

3. Senha de login hardcoded no frontend (`AuthGate.tsx`, "senha123",
   client-side, sessionStorage) — não é autenticação de verdade, qualquer
   um que leia o bundle JS vê a senha. Aceitável como paywall informal de
   MVP, mas vale substituir antes de expor o Hub além do time interno.

4. Acesso cross-project entre dev e prod (IAM desta sessão): dev faz deploy
   automático em qualquer push sem review, e agora a SA de dev lê dados
   reais de prod. Risco aceito conscientemente pelo usuário nesta sessão —
   revisitar se algum dia incomodar (ex: exigir review antes de deploy em
   dev, ou restringir o binding).

5. Revisitar a restrição de WIF de prod (refs/heads/main) se algum dia for
   necessário automatizar terraform plan de prod em PR.

6. Bundle do frontend passou de 500kB no build (524.80 kB / gzip 166kB) —
   aviso do Vite sobre code-splitting. Não é bloqueante no tamanho atual,
   mas cresce a cada domínio novo (lineage/PII/access vêm na Sprint 3).

7. Actions do CI (`actions/checkout@v4`, `google-github-actions/auth@v2`,
   `google-github-actions/setup-gcloud@v2`) alvo de Node.js 20, GitHub já
   forçando pra Node 24 com aviso de depreciação — sem ação necessária
   agora, mas vale atualizar as actions antes que vire erro.

8. ~~roles/logging.viewer não concedida em dev nem prod~~ — **obsoleto**:
   descoberto nesta sessão (2026-08-14, via `gcloud projects
   get-iam-policy`) que a role já tinha sido concedida self (cada SA no
   próprio projeto) em algum momento entre sessões, sem atualizar este
   arquivo. Cross-project (dev↔prod) foi concedida nesta própria sessão,
   ver "Bug: lineage cross-project" abaixo. Checklist completo (incluindo
   este item) agora vive em `docs/onboarding-cliente.md`.

9. ~~Data Access audit logs desabilitados em dev e prod~~ — **obsoleto**:
   mesma descoberta do item 8, `auditConfigs` já tinha `DATA_READ`,
   `DATA_WRITE` e `ADMIN_READ` habilitados pra `bigquery.googleapis.com`
   nos dois projetos antes desta sessão, também sem registro. Formalizar
   via Terraform (`google_project_iam_audit_config`) continua pendente,
   mas não é mais bloqueante — dado real já flui.

10. ~~Schema dos audit logs nunca validado contra logs reais~~ —
    **obsoleto**: resolvido nos commits `72ed011`/`f18dfab` (depois do
    último `SESSIONLOG` escrito, nunca documentado aqui) — o formato real
    em uso é `AuditData`/`jobCompletedEvent` (legado), não
    `BigQueryAuditMetadata`/`jobChange` como a doc de migração do BQ
    sugeria; parser corrigido, payload real capturado e versionado em
    `tests/unit/lineage/test_repository.py`. Ver docstring de
    `domains/lineage/repository.py`.

11. **Falha de processo recorrente: mudanças de IAM/audit config feitas
    entre sessões sem atualizar o SESSIONLOG** — itens 8/9/10 acima
    ficaram desatualizados por pelo menos uma sessão inteira porque o
    usuário rodou os comandos de IAM/audit config fora do fluxo
    documentado por este arquivo. Mitigação adotada nesta sessão: nova
    seção "Registro de acessos e configurações" no CLAUDE.md + log vivo em
    `docs/onboarding-cliente.md`, para toda concessão de acesso (IAM, API,
    audit config) ser registrada no momento em que acontece, e verificada
    (não assumida) antes de marcar como feita.

12. **Possíveis documentos órfãos na coleção `profiling_results` do
    Firestore de dev** — a feature de score de qualidade escreveu nessa
    coleção enquanto esteve ativa nesta sessão (depois revertida, ver
    Sprint 3.2 acima). Nenhum código lê ou escreve mais nela, mas os
    documentos de teste podem continuar existindo no Firestore até
    alguém limpar manualmente — não afeta nada em runtime, só
    "sujeira" de dado morto.

13. **Bundle do frontend** — 1.327,96 kB / gzip 392,71 kB (medido ao vivo
    ao fim desta sessão, 2026-08-18), depois de mais um domínio inteiro
    (`storage`) somado a lineage/FinOps/Admin. Item 6 do backlog da
    Sprint 2 (code-splitting) fica mais urgente a cada domínio novo —
    ainda não implementado. Bom candidato pra próxima sessão que não
    tenha feature nova pra entregar.

14. **Expansão de cobertura pra além do BigQuery** — **1ª frente
    concluída nesta sessão**: domínio `storage` (Cloud Storage) completo
    e validado em dev (catálogo, waste scanner, extensão de lineage —
    ver seção "Storage — domínio novo"). Ordem de prioridade planejada
    (spec `docs/specs/storage.md`, seção 1): Storage → Scheduler →
    Workflows. Scheduler/Workflows continuam não iniciados — não começar
    sem alinhamento explícito do usuário, mesma regra de antes.

15. ~~`CHANGELOG.md` desatualizado~~ — **obsoleto**: corrigido nesta
    sessão (depois de recuperar os commits presos em
    `feature/admin-usage-analytics`, ver "Storage — domínio novo" →
    "Falha de processo"). `CHANGELOG.md` e `docs/prd.md` agora refletem
    Fase 4 (FinOps) e Fase 5 (Storage) como concluídas.

16. **`docs/adr/ADR-009-acl-usuario-projeto.md` com datas incorretas** —
    cabeçalho diz "2026-08-18" e a "Nota de extensão" diz "2026-08-20",
    mas todos os commits reais da feature (`391d159`..`301fc59`) rodaram
    em 2026-08-17 (confirmado via `git log`). Provavelmente datas
    assumidas/erradas no momento da escrita do ADR, não checadas contra
    o commit real. Ainda não corrigido — CLAUDE.md diz "nunca apagar um
    ADR", então a correção certa é uma nota de erratum, não reescrever a
    data original; sinalizar ao usuário antes de mexer.

17. ~~Mudança não commitada em `infra/terraform/modules/cloud-run/
    variables.tf`~~ — **obsoleto**: descartada nesta sessão (`git
    restore`) por decisão do usuário, sem justificativa encontrada nos
    logs do Cloud Run.

18. **IAM/audit config de `storage` pendente em prod** — domínio inteiro
    validado em dev, mas `observability-hub-prod` ainda não tem nenhuma
    role `storage.*` (nem self nem cross), nem os 3 buckets mock, nem os
    jobs LOAD/EXTRACT reais pra popular lineage/waste scanner. Checklist
    completo em "Storage — domínio novo" → "Pendências pra promover em
    prod" — bloqueia o PR de `feat/storage-mvp` → `main`.

19. **Gap de `jobStatus.state != "DONE"` em todo parser de audit log do
    projeto** (lineage, access, finops) — nenhum dos três filtra jobs
    que falharam antes de virar aresta/evento. Descoberto durante a
    extensão do lineage pra bucket (item 4 do domínio storage), mas é
    pré-existente e afeta os três domínios, não só bucket. Não corrigido
    de propósito (fora do escopo daquele item) — considerar como um
    item de qualidade próprio, com spec/discussão de nível de confiança
    aceitável antes de implementar (mesma cautela já usada pra outras
    heurísticas do projeto).

20. **`Bucket.updated` (colunas "Criado em"/"Atualizado em" do catálogo
    de storage) não é o mesmo sinal que "dado ainda sendo gravado"** —
    documentado com clareza na spec (seção 5) e no CHANGELOG, mas vale
    revisitar se algum usuário real confundir os dois conceitos na
    prática. Trade-off aceito conscientemente, não é um bug.

21. ~~`cpu-throttling: false` ("CPU sempre alocada") nos 4 serviços Cloud
    Run~~ — **obsoleto**: descoberto e corrigido no fim desta sessão,
    numa investigação de custo do Cloud Run não relacionada ao domínio
    storage. Não vinha do Terraform nem do workflow de deploy — mudado
    manualmente fora do fluxo do projeto, sem registro de quando ou por
    quê. Revertido pro padrão (CPU só durante request) nos 4 serviços.
    **Sem explicação de quem/quando ligou originalmente** — se acontecer
    de novo, vale investigar antes de só reverter (pode ter sido uma
    tentativa de mitigar cold start, mas `cpu-throttling` não ajuda
    nisso, quem ajuda é `min_instance_count` > 0, que tem custo
    contínuo mais previsível e foi conscientemente mantido em 0 pelo
    projeto).
```

---

## Próxima sprint

```
Domínio storage fechado de ponta a ponta em 2026-08-18: implementado,
validado em dev, infra de prod promovida, PR #25 aberto e mergeado em
main, deploy automático de prod confirmado verde, rotas novas
confirmadas no ar via /openapi.json de prod. Nada pendente desta
sprint. Validação visual das 4 funcionalidades em prod fica a cargo do
usuário (sem Chromium headless neste sandbox, mesma limitação de
sempre).

Nenhuma sprint nova está aprovada. Candidatos conhecidos
pro próximo passo, nenhum iniciado, em ordem de menor pra maior escopo:
1. Formalizar IAM cross-project em Terraform (Backlog item 2) — cresce
   a cada domínio novo com role própria.
2. ADR-009 com datas incorretas (Backlog item 16) — sinalizar ao
   usuário antes de tocar (nunca apagar/reescrever ADR).
3. Code-splitting do bundle frontend (Backlog item 13) — 1.327,96 kB /
   gzip 392,71 kB, cresce a cada domínio novo.
4. Gap de jobStatus.state != "DONE" em lineage/access/finops (Backlog
   item 19) — precisa de spec/discussão de nível de confiança antes de
   implementar.
5. Scheduler/Workflows — próxima frente de "além do BigQuery" (Backlog
   item 14), só com alinhamento explícito do usuário.

Nenhum desses foi validado com o usuário como próxima sprint — são só o
estado observável do backlog. Perguntar antes de agir.
```

---

## Como retomar após reset

1. `cd ~/observability-hub && claude`
2. Claude Code lê CLAUDE.md + SESSIONLOG.md
3. `git fetch && git checkout main && git pull` — a `main` local fica
   desatualizada com frequência (chegou a ficar 2 sessões pra trás nesta
   mesma sprint); sempre conferir contra `origin/main` antes de assumir
   o estado, nunca só a `main` local. Estado no fim desta sessão:
   `main` = `d022061` (merge do PR #25).
4. Domínio `storage` (Cloud Storage) está **completo e fechado**: PR #25
   mergeado em `main`, deploy de prod confirmado verde. Branch
   `feat/storage-mvp` pode ser deletada (local e remota) quando
   conveniente — já está toda mergeada. `git status` na `main` deve
   estar limpo.
5. Nenhuma sprint em andamento — confirmar com o usuário qual é o
   próximo passo antes de começar qualquer implementação (ver "Storage
   — domínio novo" → "Promoção pra prod — concluída nesta
   sessão"), não precisa rodar mais nenhum comando de infra antes do PR.
6. `docs/onboarding-cliente.md` é o checklist vivo de acesso pra projetos
   alvo (cliente ou dev/prod um observando o outro) — qualquer sessão que
   conceder/alterar IAM, API ou audit config num projeto deve registrar lá
   antes de considerar a tarefa concluída (ver CLAUDE.md, "Registro de
   acessos e configurações"). Está em dia até 2026-08-18.
7. **Lição desta sessão, não repetir**: commits de documentação numa
   branch de feature só são confiáveis depois de mergeados em `main` via
   PR — presos numa branch (mesmo pusheados pro remoto), somem quando
   uma branch nova nasce de `main` atualizada. Ver "Storage — domínio
   novo" → "Falha de processo".
