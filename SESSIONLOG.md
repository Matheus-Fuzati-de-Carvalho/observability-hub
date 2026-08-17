# SESSIONLOG — Observability Hub

Arquivo de continuidade de sessão. Atualizado pelo Claude Code antes de resets.
Lido obrigatoriamente no início de cada nova sessão após um reset.

---

## Status atual

**Última atualização:** 2026-08-17 — reconstrução completa a partir do
histórico real de commits/PRs (`git log`, `gh pr list`, specs e ADRs),
porque o SESSIONLOG não foi atualizado desde 2026-08-14 (commit `5741ae7`)
apesar de **quatro dias inteiros de trabalho** terem acontecido nesse
meio-tempo — mesma falha de processo já registrada antes neste arquivo
(ver Backlog item 11), desta vez numa escala bem maior. Sessão atual não
implementou nada — só leu o estado real do repositório e desta vez
**escreveu o SESSIONLOG antes de qualquer outra tarefa**, em vez de
depois.

**Estado real agora:** todo o trabalho de Sprint 3.2 (fechamento), FinOps
completo (3 frentes) e Admin ACL (v1.0 a v1.3) **já está mergeado em
`main` e deployado em prod**, via PRs #18 a #24. A branch local
`feature/admin-usage-analytics` (HEAD `0461b36`) é **idêntica** ao
merge-base com `origin/main` (`origin/main` = `35c0205`, merge do PR
#24) — ou seja, não há nada pendente de merge nesta branch; ela só
ainda não foi limpa/deletada localmente. A `main` local (`44ad7c9`) está
desatualizada (ainda no PR #17) e precisa de `git pull`/`fetch` antes de
qualquer trabalho novo a partir dela — só o remoto (`origin/main`) reflete
o estado real.

**Único item pendente nesta sessão:** `infra/terraform/modules/cloud-run/
variables.tf` tem uma mudança **não commitada, não staged** —
`max_instance_count` default `2` → `5` — sem contexto de por que ou pra
qual ambiente na conversa atual. Não faz parte de nenhum PR listado
acima. Perguntar ao usuário antes de commitar (contexto de IaC exige
`terraform plan` revisado + aprovação antes de qualquer apply, ver
CLAUDE.md).

**Sprints/fases concluídas desde a última atualização real do log:**

1. ✅ **Sprint 3.2 completa (7 de 7 itens)** — os 2 itens que faltavam
   (PII, mapa de acesso) mais lineage evoluindo de 1-hop pra grafo
   transitivo multi-hop cross-project. PR #18.
2. ✅ **FinOps completo (as 3 frentes do roadmap, Fase 4 do CHANGELOG)**
   — scanner de desperdício (PR #19), budget de custo por
   dataset/usuário/dia/mês/ano (PR #20), sugestão de tipo de coluna (PR
   #20/#21). **`CHANGELOG.md` ainda diz Fase 4 "em andamento, falta
   otimizações sugeridas" — isso está desatualizado, a spec
   `finops-column-types.md` v1.1 está com `Status: Aprovada` e é a
   última coisa implementada dessa frente.** Ver Backlog.
3. ✅ **Admin ACL v1.0 → v1.3** (ADR-009) — segunda camada de
   autorização usuário×projeto (fail closed), tela `/admin`, projetos
   públicos, solicitação de acesso self-service, e um painel de
   analytics de uso do próprio Hub (aba "Uso do Hub" — de onde vem o
   nome da branch `feature/admin-usage-analytics`: logins, favoritos
   entre usuários, atividade de profiling/PII, solicitações de acesso,
   navegação agregada). PRs #20, #21.
4. ✅ **Documentação para cliente** — dois playbooks operacionais
   (`docs/playbooks/`) e dois manuais voltados a cliente final
   (`docs/manual-implementacao-cliente.md`,
   `docs/manual-liberacao-acesso-cliente.md`). PRs #22, #23, #24.
5. ✅ Duas reorganizações de sidebar (agrupamento por tópico, depois
   hierarquia por serviço observável — `SidebarServiceGroup`,
   deliberadamente pronta pra um serviço GCP além do BigQuery).

Ver as seções próprias abaixo ("Sprint 3.2 — fechamento", "FinOps",
"Admin ACL", "Documentação para cliente", "Sidebar") para o detalhe
técnico de cada uma, reconstruído a partir de commits/specs/ADRs — não
de memória de sessão, já que nenhuma sessão anterior deixou notas.

**Próximo passo:** confirmar com o usuário o contexto da mudança não
commitada em `variables.tf` (`max_instance_count`); depois, perguntar
qual é o próximo item de trabalho — não há nenhuma spec pendente nem
sprint em andamento no momento. Candidatos conhecidos, nenhum iniciado:
Backlog item 14 (expansão de cobertura pra além do BigQuery, adiada
conscientemente pelo usuário em 2026-08-17), atualizar `CHANGELOG.md`/
`docs/prd.md` (roadmap desatualizado desde a Sprint 3.2), e formalizar
IAM cross-project em Terraform (Backlog item 2, cada vez mais adiado).

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
├── Cloud Run: backend ✅ tag 0461b36 (feature/admin-usage-analytics —
│   última mudança de app real foi no PR #21, 22/23/24 são docs-only e
│   não disparam deploy)
├── Cloud Run: frontend ✅ tag 0461b36, idem
├── Artifact Registry: apps ✅ (compartilhado backend+frontend)
├── IAM backend-run@...-dev: metadataViewer + jobUser + dataViewer +
│   logging.viewer + logging.privateLogViewer no próprio projeto e em
│   observability-hub-prod (cross-project completo nas 5 roles — a
│   privateLogViewer cross foi a última peça, confirmada via
│   `gcloud projects get-iam-policy` em 2026-08-17)
├── IAM backend-run@...-prod: as mesmas cinco roles em observability-hub-dev
│   (cross-project completo, idem)
├── Data Access audit logs (DATA_READ, DATA_WRITE, ADMIN_READ) habilitados
│   em dev e prod pra bigquery.googleapis.com
├── Checklist completo de IAM/API/audit config pra onboarding de projeto
│   alvo vive em docs/onboarding-cliente.md — registro de concessões
│   (tabela "Registro de acessos concedidos") está em dia até 2026-08-17
├── Firestore (Native mode): hub_users, hub_projects, access_requests,
│   login_events, users/{email}/{favorites,history_*}, profiling_history,
│   pii_scan_history — todas coleções/subcoleções próprias do Hub, SA de
│   runtime já tinha datastore.user no próprio projeto (sem role nova)
├── Admin seedado (scripts/seed_admin.py) — confirmado antes do PR #20
├── Pipeline: 556 testes unitários backend, 100% passando, ruff limpo;
│   frontend tsc/biome/vite build limpos; deploy automático verde a cada
│   push (gh run list confirmado até 2026-08-17)
└── Datasets mock: RAW (3 tabelas), TRUSTED (2 tabelas), REFINED (1 view)

GCP Prod (observability-hub-prod)
├── Cloud Run: backend ✅ tag c893c60 (merge commit do PR #21 — última
│   mudança de app; PR #22/23/24 são docs-only, sem deploy)
├── Cloud Run: frontend ✅ tag c893c60, idem
├── Artifact Registry: apps ✅ (compartilhado backend+frontend)
├── IAM: ver bloco de dev acima — simétrico nas duas direções, sem lacunas
│   conhecidas no momento
├── Admin ACL passou a gatear 9 routers em prod pela primeira vez no PR
│   #20 (admin seedado em prod antes do merge, conforme corpo do PR)
├── total_datasets: 3
└── WIF: attribute_condition restrito a refs/heads/main (só push direto,
    nunca PR) — plan de prod continua revisão manual

GitHub Secrets
├── WIF_PROVIDER_DEV ✅
├── WIF_SA_DEV ✅
├── WIF_PROVIDER_PROD ✅
└── WIF_SA_PROD ✅

main/prod e a branch feature/admin-usage-analytics estão no MESMO ponto
(origin/main = 35c0205 = merge do PR #24 = HEAD da branch). Não há
trabalho de app pendente de merge. A `main` LOCAL está desatualizada
(44ad7c9, PR #17) — rodar `git fetch && git checkout main && git pull`
antes de criar qualquer branch nova a partir dela.

Único estado não commitado no working tree: `infra/terraform/modules/
cloud-run/variables.tf` (`max_instance_count` 2→5) — ver "Status atual".
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
confirmado via `gh pr list --state all` e `git log origin/main`. Não há
sprint em andamento nem PR aberto no momento desta atualização.

---

## Backlog / dívida técnica identificada

```
Bloqueantes de nenhuma fase, considerar quando aparecer necessidade:

1. ~~Datasets com apenas views não exibem indicador de freshness na
   sidebar~~ — **obsoleto**: Sprint 2.3 removeu os indicadores de status
   SLA da sidebar por completo (pedido do usuário, não relacionado a este
   item). Não há mais bolinha de nenhum tipo ali.

2. Formalizar IAM (bigquery.metadataViewer/jobUser/dataViewer, incluindo os
   bindings cross-project desta sessão) em Terraform em vez de gcloud
   manual — mais urgente agora que existem 6 bindings manuais por projeto
   (3 roles x 2 SAs) em vez de 2. Fica mais fácil de perder rastro sem IaC.

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

13. **Bundle do frontend** — estava em 929.60 kB / gzip 281 kB no fim da
    Sprint 3.2 (antes de FinOps/Admin), e ganhou mais duas dependências
    desde então (`@xyflow/react` + `dagre`, pro diagrama de lineage
    multi-hop) — tamanho atual não medido nesta reconstrução (não rodei
    `vite build` completo). Item 6 do backlog da Sprint 2
    (code-splitting) fica mais urgente a cada domínio novo — ainda não
    implementado. Medir de novo na próxima sessão que tocar frontend.

14. **Expansão de cobertura pra além do BigQuery** — hoje os 7 domínios
    (catálogo, lineage, PII, mapa de acesso, qualidade, freshness,
    FinOps) só observam BigQuery/Cloud Logging/Cloud Billing. Cliente
    (via usuário, 2026-08-17) confirmou interesse em mapear outros
    serviços GCP do lado do cliente (ex: Cloud Storage, Pub/Sub,
    Dataflow) no futuro, mas decidiu conscientemente adiar. A
    reorganização de sidebar em `SidebarServiceGroup` (commit `94629a6`,
    mesma data) já deixa a estrutura de navegação pronta pra isso sem
    retrabalho. Não iniciar sem alinhamento explícito do usuário.

15. **`CHANGELOG.md` desatualizado** — a tabela "Próximas fases" ainda
    lista Fase 4 (FinOps) como "⏳ Em andamento... falta otimizações
    sugeridas", e não existe nenhuma seção "O que foi feito" pra Sprint
    3.2 (fechamento), FinOps ou Admin ACL — só a Sprint 2.2/2.3 é a mais
    recente documentada lá. `docs/prd.md` (seção de roadmap) provavelmente
    tem a mesma defasagem, não verificado nesta reconstrução. Não
    corrigido nesta sessão (fora do pedido explícito de só atualizar o
    SESSIONLOG) — próxima sessão que tocar documentação deveria fechar
    isso, CLAUDE.md pede atualização de CHANGELOG a cada fase concluída.

16. **`docs/adr/ADR-009-acl-usuario-projeto.md` com datas incorretas** —
    cabeçalho diz "2026-08-18" e a "Nota de extensão" diz "2026-08-20",
    mas todos os commits reais da feature (`391d159`..`301fc59`) rodaram
    em 2026-08-17 (confirmado via `git log`). Provavelmente datas
    assumidas/erradas no momento da escrita do ADR, não checadas contra
    o commit real. Não corrigido nesta sessão — CLAUDE.md diz "nunca
    apagar um ADR", então a correção certa é uma nota de erratum, não
    reescrever a data original; sinalizar ao usuário antes de mexer.

17. **Mudança não commitada em `infra/terraform/modules/cloud-run/
    variables.tf`** (`max_instance_count` default `2` → `5`) — sem
    contexto na conversa desta sessão sobre motivo ou ambiente-alvo.
    Não commitado, não staged. Perguntar ao usuário antes de qualquer
    `terraform plan`/commit (contexto de IaC do CLAUDE.md exige plan
    revisado + aprovação).
```

---

## Próxima sprint

```
Não há sprint em andamento nem spec pendente no momento desta
atualização (2026-08-17). Tudo que estava planejado até aqui (Sprint
3.2, FinOps 3 frentes, Admin ACL v1.0-v1.3, docs pra cliente) está
concluído e mergeado em main/prod.

Candidatos pro próximo passo, nenhum iniciado, em ordem de menor pra
maior escopo:
1. Resolver a mudança não commitada em variables.tf (Backlog item 17)
   — perguntar ao usuário o que ela é antes de qualquer coisa.
2. Fechar a documentação defasada: CHANGELOG.md (Backlog item 15) e
   possivelmente docs/prd.md — marcar Fase 4/Sprint 3.2/Admin como
   concluídas, registrar erros/aprendizados da sessão de 2026-08-17
   (bug de regiões fantasma no finops budget é o mais rico pra registrar).
3. Formalizar IAM cross-project em Terraform (Backlog item 2) — agora
   são 5 roles x 2 SAs = 10 bindings manuais por direção, cada vez mais
   trabalhoso de auditar só via gcloud.
4. Expansão de cobertura pra além do BigQuery (Backlog item 14) — só
   com alinhamento explícito do usuário, decisão consciente de adiar.

Nenhum desses foi validado com o usuário nesta sessão — são só o estado
observável do backlog, não um plano aprovado. Perguntar antes de agir.
```

---

## Como retomar após reset

1. `cd ~/observability-hub && claude`
2. Claude Code lê CLAUDE.md + SESSIONLOG.md
3. `git fetch && git checkout main && git pull` — a `main` local está
   desatualizada (`44ad7c9`, PR #17); o estado real são os PRs #18–#24,
   todos mergeados em `origin/main` (`35c0205`). A branch local
   `feature/admin-usage-analytics` é idêntica ao merge-base com
   `origin/main` — não tem nada pendente de merge, só não foi limpa.
4. Checar `git status` antes de qualquer coisa — há uma mudança não
   commitada em `infra/terraform/modules/cloud-run/variables.tf`
   (`max_instance_count` 2→5) sem contexto registrado; perguntar ao
   usuário o que é antes de tocar nela.
5. Não há sprint em andamento — confirmar com o usuário qual é o
   próximo passo antes de começar qualquer implementação (ver "Próxima
   sprint" acima pra candidatos conhecidos, nenhum aprovado ainda).
6. `docs/onboarding-cliente.md` é o checklist vivo de acesso pra projetos
   alvo (cliente ou dev/prod um observando o outro) — qualquer sessão que
   conceder/alterar IAM, API ou audit config num projeto deve registrar lá
   antes de considerar a tarefa concluída (ver CLAUDE.md, "Registro de
   acessos e configurações"). Está em dia até 2026-08-17.
