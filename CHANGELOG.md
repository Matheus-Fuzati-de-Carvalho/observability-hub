# CHANGELOG — Observability Hub

Histórico de fases, decisões, erros cometidos e pivotagens.
Atualizado ao final de cada fase pelo Claude Code.

---

## CI/CD: gate de aprovação manual antes de deploy de app em prod

Direto em `main`, fora de qualquer sprint — pedido do usuário depois de
investigar um custo de Cloud Run maior que o normal (ver item abaixo).

### O que foi feito
`backend-deploy-prod.yml`/`frontend-deploy-prod.yml` ganharam
`environment: production` no job de deploy — GitHub segura o job em
"Waiting" até alguém aprovar manualmente (Settings → Environments →
`production`, "Required reviewers"), em vez de publicar sozinho a cada
push em `main`. `terraform-apply-prod.yml` continua automático, de
propósito: mudança de infra já passa por `terraform plan` revisado
antes do merge, diferente do deploy de app, que sobe uma imagem nova
sem revisão nenhuma no meio. `dev` não muda — continua 100% automático.

### Nota sobre a primeira aplicação (corrida de tempo)
No dia em que o gate foi configurado, o `backend-deploy-prod.yml` do
push seguinte ficou corretamente em "Waiting", mas o
`frontend-deploy-prod.yml` do mesmo push **não** — já estava
`in_progress` quando a regra de proteção do environment foi salva.
Deploy único, sem gate, não repetido depois — não é um problema na
configuração, é só o tipo de corrida que só acontece na primeira vez
que a regra é criada.

### Diagnóstico de custo do Cloud Run (achado no caminho, não relacionado ao domínio storage)
Investigando por que um dia teve custo bem maior que os outros: os 4
serviços Cloud Run (dev/prod × backend/frontend) estavam com
`run.googleapis.com/cpu-throttling: false` ("CPU sempre alocada" —
cobra pelo tempo de vida da instância inteira, não só durante o
processamento da requisição). Confirmado que não vinha do Terraform
(`resources.cpu_idle` não é declarado no módulo `cloud-run`) nem do
workflow de deploy (nenhum dos 4 passa essa flag) — foi mudado
manualmente fora do fluxo do projeto, sem registro de quando ou por
quê. Revertido pro padrão (CPU só durante request) nos 4 serviços,
confirmado com `gcloud run services describe` + health check 200 nos
4 depois do rollout. `min_instance_count = 0` (scale-to-zero) confirmado
intacto nos 4 — nunca foi a causa.

Volume de requisições do dia em questão (dev 1163, prod 37) bateu com
um dia de implementação intensa (a própria sprint do domínio storage) —
não foi um vazamento de tráfego, foi o multiplicador de custo do CPU
sempre alocado em cima de um dia de uso real e alto.

---

## Auditoria completa de documentação de acesso e hospedagem

Pedido explícito do usuário: revisão de ponta a ponta de toda a
documentação que será entregue a terceiros (para liberar acesso a
projetos-alvo) e usada pelo próprio usuário (para hospedar o Hub do
zero em outra conta/repositório GitHub). Achados e correções:

- `docs/playbooks/liberar-projeto-para-o-hub.md` e
  `docs/manual-liberacao-acesso-cliente.md` **não mencionavam o domínio
  `storage` de forma alguma** (escritos antes da Fase 5) — nenhuma das
  duas roles de storage, nenhuma API, nenhum audit log. Atualizados com
  a seção completa (API, as 2 roles sempre juntas, audit log opcional
  com aviso de volume, checklist, troubleshooting).
- `docs/onboarding-cliente.md`: introdução citava só 4 dos 8 domínios;
  tabela de roles não creditava `pii`/`access`/`finops` como
  consumidores das roles já listadas; justificativa de "`billing.viewer`
  não necessário" ainda dizia "FinOps não implementado" (implementado
  há dias). Todos corrigidos.
- **Achado crítico nos dois playbooks de hospedagem**
  (`hospedar-hub-em-novo-projeto.md`, `manual-implementacao-cliente.md`):
  a escolha de nome dos dois projetos GCP nunca foi documentada como
  **obrigatória** terminar em `-dev`/`-prod` — só aparecia como exemplo
  sugerido. `core/secrets.py::_is_prod()` decide qual par de secrets
  OAuth ler checando literalmente `project_id.endswith("-prod")`; um
  nome fora desse padrão faz login de prod ler secrets de dev
  silenciosamente, sem erro. Adicionado como aviso obrigatório, item de
  checklist e linha de troubleshooting nos dois documentos.
- Os dois playbooks de hospedagem também ganharam o passo de configurar
  o `environment: production` do GitHub (ver seção de CI/CD acima) — sem
  isso, replicar o repositório copia os workflows já gateados, mas sem
  a regra de proteção configurada o gate simplesmente não existe.

Nenhuma mudança de código nesta sessão — só documentação.

---

## Fase 5 — Storage (Cloud Storage): domínio novo, 4 itens (concluída, validada em dev)

Branch `feat/storage-mvp`, a partir de `main` pós-PR #24. Primeira
expansão do Hub pra além do BigQuery (spec `docs/specs/storage.md`,
motivação registrada lá: Storage → Scheduler → Workflows é a ordem de
prioridade planejada). Quatro itens, cada um validado em dev pelo usuário
antes do próximo começar, nenhum PR pra `main` ainda.

### 1. Catálogo de buckets
`GET /api/v1/storage/{project}/buckets` — nome, storage class, região,
tamanho total + contagem de objetos (via listagem cacheada 5min, mesmo
padrão de `core/bigquery.py::get_table_cached`), `has_lifecycle_rule`,
`time_created`/`updated` (metadado nativo do `Bucket`, de graça na mesma
chamada). Novo `core/storage_client.py`, novo grupo `SidebarServiceGroup`
"Cloud Storage" na sidebar (irmão de "BigQuery").

**Bug real encontrado em dev**: `roles/storage.objectViewer` (única role
que a v1 da spec previa) não cobre `storage.buckets.list`/`storage.
buckets.get` — só `storage.objects.*`. `list_buckets()` (a primeira
chamada do domínio) precisa também de `roles/storage.bucketViewer`
(role dedicada, só leitura de metadado de bucket). Confirmado com
`gcloud iam roles describe`, corrigido no handler de 403 e no checklist
de `docs/onboarding-cliente.md` (as duas roles, sempre juntas).

### 2. Freshness — implementada, validada, depois substituída
V1: endpoint dedicado (`GET .../buckets/{bucket}/freshness`), botão "Ver
freshness" sob demanda no frontend, `last_modified` = `max(customTime ou
updated)` entre os **objetos** do bucket. Validada em dev e então
**descartada por decisão do usuário**, substituída por `time_created`/
`updated` do próprio `Bucket` (item 1) como colunas direto na tabela —
mais barato (zero chamada extra), mas semanticamente diferente:
`Bucket.updated` reflete mudança de config (lifecycle, storage class),
não gravação de objeto. Trade-off registrado explicitamente na spec
(seção 5) — código da v1 removido por completo, não deixado como dead
code.

### 3. Scanner de desperdício — duas checagens independentes
`GET /api/v1/storage/{project}/waste-candidates?min_days_unused=30|60|90`
(`IntEnum`, mesma correção de `Literal`→422 já feita no FinOps):
- **6.1 (config-based)**: bucket sem lifecycle rule + objetos `STANDARD`
  mais antigos que o threshold. Sempre disponível, só metadado.
- **6.2 (usage-based, pedido numa segunda rodada depois de habilitar
  Data Access audit log `DATA_READ` do GCS em dev)**: objeto elegível por
  6.1 sem nenhuma leitura (`storage.objects.get`) nos audit logs em 90
  dias ganha `confidence: "usage_confirmed"`. Payload do audit log de GCS
  é o proto padrão `google.cloud.audit.AuditLog` — **diferente** do
  formato legado que lineage/access usam pra job do BigQuery, parser novo
  em `domains/storage/repository.py::list_read_object_keys`, mesmo client
  de Cloud Logging (roles já cross-granted). Degradação graciosa
  obrigatória: `Forbidden` ou resultado vazio pro projeto inteiro (audit
  log pode estar desabilitado) nunca falha a requisição — cai pra
  `config_based` em todos os candidatos, com `usage_check_warning`
  explicando o motivo.

Faixa de economia (nunca valor único) reflete migração pra `NEARLINE`
(mínimo) ou `COLDLINE` (máximo) sobre bytes reais armazenados —
`ARCHIVE` fica de fora de propósito (retrieval caro + duração mínima de
365 dias).

**Gap pré-existente encontrado, corrigido junto** (não era novo deste
item): `list_bucket_objects_cached` não capturava `Forbidden` — um
projeto com `bucketViewer` mas sem `objectViewer` estourava 500 cru em
vez do 403 limpo do domínio. `repository.py` ganhou `project_id` nos
parâmetros de listagem de objetos pra poder relançar
`StorageAccessDeniedError`.

### 4. Extensão do lineage — bucket como nó do grafo
`load` (GCS→BQ) vira aresta bucket→tabela; `extract` (BQ→GCS) vira aresta
tabela→bucket. Payloads reais capturados ao vivo em dev (gravação real de
objeto + `gcloud logging read`) usados como fixture de teste, não
inventados. `JobEvent` ganhou `source_buckets`/`destination_buckets`;
`NodeRef` (service.py) generaliza `TableRefTuple` (3-tupla) +
`BucketRef` (1-tupla) — discriminável só pelo tamanho da tupla.

**Decisão de desenho tomada com o usuário**: bucket é sempre nó **folha**
— entra no grafo quando descoberto pelos eventos já buscados do lado
tabela, mas a travessia BFS nunca expande a partir dele. Diferente de
tabela, bucket não tem "projeto dono" confiável via API pra saber em qual
audit log procurar quem mais o referencia (nome do bucket não garante o
projeto GCP dono, e jobs que o tocam podem rodar em qualquer projeto
observado pelo Hub). `LineageNode` ganhou `type`/`bucket_name`;
`project_id`/`dataset_id`/`table_id` viraram opcionais. Frontend:
`bucketNode` novo em `LineageGraph.tsx` (ícone `HardDrive`, cor
`status-ok`).

**Gap encontrado, deliberadamente não corrigido** (fora do escopo deste
item — é do domínio `lineage` inteiro, não específico de bucket): nenhum
parser de audit log do projeto (lineage, access, finops) filtra
`jobStatus.state != "DONE"` — um job que falhou mas tem `destinationTable`/
`sourceUris` no config já criaria uma aresta hoje. Registrado como
backlog do domínio lineage na spec.

### Falha de processo encontrada e corrigida durante esta sessão
Commits de fechamento do SESSIONLOG/CHANGELOG de uma sessão anterior
(reconstrução completa depois de 4 dias sem atualização, ver seção
"Documentação para cliente" abaixo) tinham ficado presos na branch
`feature/admin-usage-analytics` — nunca foram mergeados em `main` via PR,
só pusheados pra o remoto da própria branch. Quando `feat/storage-mvp`
foi criada a partir de `main` atualizada, herdou a versão **velha** do
SESSIONLOG (de 2026-08-14). Descoberto e corrigido nesta sessão com um
merge explícito de `feature/admin-usage-analytics` em `feat/storage-mvp`
antes do fechamento de documentação — sem isso, a reconstrução de 4 dias
de trabalho teria se perdido uma segunda vez.

### Status final
- Backend: 597 testes unitários (0 no início do domínio storage), 100%
  passando, `ruff check`/`ruff format` limpos.
- Frontend: `biome check`, `tsc -b`, `vite build` limpos.
- Validado em dev pelo usuário — os 4 itens, incluindo o grafo de lineage
  com bucket real (`RAW.crm_leads_staging` ⟷ buckets `landing`/
  `processed`, jobs LOAD/EXTRACT reais).
- Infraestrutura de prod promovida antes do merge (IAM, buckets, mocks,
  audit config — checklist em `docs/onboarding-cliente.md`) e deploy
  automático confirmado verde depois (`gh run list`).
- **PR #25 mergeado em `main`, deployado em prod.**

---

## Documentação para cliente — playbooks operacionais e manuais (PRs #22, #23, #24)

Branch `feature/admin-usage-analytics`, três commits **docs-only** (não
tocam `apps/`, sem deploy disparado — confirmado via `gh run list`).
Fecha o ciclo iniciado por `docs/onboarding-cliente.md` (checklist
técnico) com material de execução e material voltado a cliente final,
todos referenciando o mesmo checklist e os ADRs 006/009 como fonte de
verdade técnica.

### O que foi feito

**Dois playbooks internos** (`docs/playbooks/`, público: time do Hub):
1. `liberar-projeto-para-o-hub.md` (216 linhas) — roteiro de "já tenho um
   projeto GCP com dados, o que preciso fazer pra o Hub ler esse
   projeto". Explicitamente não é fonte de verdade — aponta pra
   `docs/onboarding-cliente.md` pra isso, e pede que quem executar volte
   lá pra registrar a concessão. Deixa claro que a liberação de
   infraestrutura GCP é só metade do caminho — a segunda camada (ACL do
   Hub, ADR-009) é liberada depois, dentro do próprio `/admin`.
2. `hospedar-hub-em-novo-projeto.md` (449 linhas) — roteiro de "quero
   rodar minha própria cópia do Hub em projetos GCP diferentes dos
   originais, do zero". Bootstrap único por par de ambientes (dev/prod);
   depois de concluído, o dia a dia vira só `git push`. Cobre o
   inventário completo de infraestrutura que o Hub precisa pra existir
   (2 Cloud Run, Artifact Registry compartilhado, SAs de runtime,
   Firestore, Secret Manager, WIF, bucket GCS de state).

**Dois manuais voltados a cliente final** (linguagem sem jargão interno):
3. `docs/manual-implementacao-cliente.md` (361 linhas) — implementação de
   uma instância própria do Hub no GCP do cliente, hospedagem/
   administração sob controle dele. Seção "Segurança e escopo" explícita:
   tudo dentro dos projetos do próprio cliente, sem credencial de longa
   duração (WIF), permissões mínimas, reversível, nada trafega pra fora
   do ambiente GCP dele. Público: responsável técnico com papel *Owner*.
4. `docs/manual-liberacao-acesso-cliente.md` (197 linhas) — contraparte de
   `liberar-projeto-para-o-hub.md`, em linguagem de cliente: como
   autorizar o Hub (já hospedado) a ler um projeto GCP existente. Mesma
   seção "o que faz/não faz": só leitura, nada instalado no projeto do
   cliente, acesso escopado e revogável, cliente confirma cada permissão
   antes de conceder. Público: *Owner*/*IAM Admin*. Tempo estimado
   10–15min (vs. meio dia do manual de implementação).

### Decisões desta sessão

**Decisão 1 — Quatro documentos, não dois, por causa da audiência**
- Playbook interno (linguagem do time do Hub, assume contexto do
  CLAUDE.md/ADRs) e manual de cliente (linguagem sem jargão, assume
  Owner de um GCP que nunca ouviu falar do Hub) são públicos diferentes
  o bastante pra não caber no mesmo texto — cada par (liberar acesso /
  hospedar o Hub) ganhou uma versão de cada.

### Status até o momento
- Docs-only, sem impacto em testes/build/deploy.
- Nenhum projeto de cliente real usou os manuais ainda — primeira
  validação de uso real fica pra quando isso acontecer.

---

## Admin — refactor de colunas/filtros e UX de listas longas (commits `568622a`, `301fc59`)

Branch `feature/admin-usage-analytics`. Depois da v1.3 (seis seções de
analytics simultâneas na aba "Uso do Hub"), dois ajustes de qualidade
antes de fechar a frente de Admin.

### O que foi feito
1. **Padronização de colunas/filtros (`568622a`)**: as seis seções tinham
   crescido cada uma com sua própria tabela ad-hoc (nomes de coluna
   diferentes pra projeto/dataset/tabela, filtros inconsistentes entre
   seções). Refatorado pra um padrão único de colunas e filtros
   compartilhado entre todas.
2. **Tópicos recolhíveis + paginação (`301fc59`)**: as seis seções
   (Acessos, Favoritos, Profiling, Solicitações, Navegação, Scans de
   PII) e seus sub-blocos nomeados (ex: "Bases mais favoritadas",
   "Drill-down") passaram a usar `CollapsibleSection` — abrem por
   padrão, mas podem ser recolhidas. Toda lista tabular ganhou paginação
   client-side de verdade via `usePagination`/`PaginationBar`
   (10/20/50/100 linhas por página) dentro de um container com scroll
   vertical, em vez de despejar a lista inteira na tela.

### Status até o momento
- Backend: sem mudança de API — refactor e paginação são só frontend.
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos.
- Validação visual fica a cargo do usuário após deploy em dev.

---

## Admin v1.3: solicitações de acesso, navegação agregada, atividade de scans de PII

Branch `feature/admin-usage-analytics` (mesma do Admin v1.2, ainda sem
push/PR). Usuário pediu um brainstorm de que outros serviços/
funcionalidades já existentes valeria mapear no painel "Uso do Hub" —
escolheu, em ordem de custo/valor, os 3 desta rodada; deixou expansão
pra serviços GCP fora do BigQuery registrada como backlog
(`SESSIONLOG.md`, item 14), adiada por decisão explícita.

### O que foi feito

Mais 3 seções na aba "Uso do Hub":

1. **Solicitações de acesso** — zero gravação nova. `access_requests`
   (já existia desde a v1.1) já tinha tudo; nova leitura agrega por mês
   (`{period, total, approved, denied, pending}`), lista os 10 projetos
   mais pedidos e calcula taxa de aprovação (`null` se nada foi
   resolvido ainda, não `0%`). Gráfico de barras empilhado por status.
2. **Navegação agregada** — zero gravação nova. `domains/history` já
   persistia `history_table_views`/`history_searches` por usuário; nova
   leitura via `collection_group` agrega entre todos (mesmo padrão de
   favoritos). "Tabelas mais vistas" (gráfico de barras horizontal) +
   "buscas mais frequentes" (tabela). Ressalva explícita na UI: cada
   usuário só guarda os 20 itens mais recentes, é uma métrica de uso
   recente, não histórico completo.
3. **Atividade de scans de PII** — gravação nova, mesmo padrão do
   profiling. `domains/pii` não persistia nada até aqui (só cache em
   memória, TTL 5min, sem usuário). Novo `history_repository.py` grava
   em `pii_scan_history/{doc}/scans` a cada execução real (não em cache
   hit). Tabela de atividade idêntica à de profiling.

### Decisões desta sessão

**Decisão 1 — Nome de subcoleção `scans`, não `runs`, pro histórico de PII**
- Achado durante a investigação, não pedido pelo usuário: profiling já
  usa `collection_group("runs")` pra agregação global. Se PII também
  usasse `runs` como nome de subcoleção, a mesma query passaria a
  devolver os dois históricos misturados — `collection_group` ignora o
  caminho do documento-pai, só olha o nome da subcoleção. Confirmado
  por grep antes de implementar que nenhum domínio usava `scans`.

**Decisão 2 — Histórico de PII só grava em execução real, não em cache hit**
- `run_pii_scan` tem cache em memória (TTL 300s) que devolve o mesmo
  resultado sem recomputar. Gravar histórico incondicionalmente faria
  um cache hit parecer uma execução nova (mesmo `executed_at`/
  `executed_by` de uma ação que não aconteceu de fato). A gravação fica
  só no branch de cache miss.

**Decisão 3 — Listas achatadas com agregação client-side, mesmo padrão da v1.2**
- Solicitações de acesso é a exceção (agregação já pronta no backend,
  porque o volume é pequeno e as métricas — mês/status/projeto — são
  fixas); navegação segue o padrão de favoritos (lista achatada, front
  agrega do jeito que precisar) porque "top tabelas"/"top buscas" são
  cálculos simples e mantém o backend sem opinião sobre quantos itens
  mostrar.

### Status até o momento
- Backend: 556 testes unitários, 100% passando, `ruff check`/`ruff
  format --check` sem erros.
- Frontend: `tsc --noEmit` limpo, `pnpm lint` (biome) sem erros,
  `pnpm build` concluído (bundle: 1.311 kB / gzip 389 kB — backlog de
  code-splitting, item 12 do `SESSIONLOG.md`, cresce a cada rodada).
- Validação visual (gráficos novos, números batendo) fica a cargo do
  usuário após deploy em dev.

---

## Admin v1.2: painel de uso/gestão — acessos ao Hub, favoritos entre usuários, atividade de profiling

Branch `feature/admin-usage-analytics`. Brainstorm do usuário: quer
visão gerencial de uso do Hub em `/admin` — acessos por dia/semana/mês,
quem acessou e quando, bases mais favoritadas, favoritos por usuário (e
o inverso), histórico de quais tabelas tiveram profile executado.

### O que foi feito

Nova aba "Uso do Hub" em `/admin`, com três seções:

1. **Acessos ao Hub** — login era 100% stateless até aqui (JWT em
   cookie, nenhum registro em lugar nenhum). Nova coleção Firestore
   `login_events/{auto_id}` (email + `logged_in_at`), gravada
   best-effort em `POST /auth/callback` (falha na gravação nunca
   derruba o login). KPIs (hoje/semana/mês + usuários únicos), gráfico
   de tendência diária, tabela de acessos recentes.
2. **Favoritos entre usuários** — `domains/favorites` só tinha visão
   por usuário (`users/{email}/favorites/`); nova leitura via
   `collection_group("favorites")` agrega todo mundo. "Bases mais
   favoritadas" (top 10) + drill-down bidirecional (usuário → itens
   favoritados, base → usuários que favoritaram), pedido explícito do
   usuário ("nos dois sentidos").
3. **Atividade de profiling** — `domains/quality/history_repository.py`
   já gravava `executed_by`/`executed_at` por tabela; ganhou também
   `project_id`/`dataset_id`/`table_id` dentro de cada run (antes só
   existiam implícitos no ID do documento-pai, sem como parsear de volta
   com segurança) pra permitir uma leitura global via
   `collection_group("runs")`.

### Decisões desta sessão

**Decisão 1 — Login events em Firestore, não Cloud Logging**
- Perguntado e confirmado com o usuário. Cloud Logging já mordeu o
  projeto duas vezes (`roles/logging.privateLogViewer` — falha
  silenciosa sem essa role, ver `docs/onboarding-cliente.md`); Firestore
  é consistente com o resto do app (favorites/history/admin) e muito
  mais simples de agregar por dia/semana/mês.

**Decisão 2 — Drill-down bidirecional de favoritos, não só contagem**
- Perguntado e confirmado com o usuário ("nos dois sentidos"). Resolvido
  com um único endpoint retornando a lista achatada de favoritos (com
  `owner_email` derivado do path do Firestore) — o front-end agrupa dos
  dois lados a partir do mesmo payload, sem precisar de dois endpoints
  nem agregação server-side.

**Decisão 3 — `unique_users` além de `login_count` por bucket**
- Não pedido explicitamente, mas adicionado como boa prática de mercado
  (padrão DAU/WAU/MAU) — mesma passada em Python que agrupa por
  dia/semana/mês já computa isso sem custo extra de leitura no Firestore.

**Decisão 4 — Agregações via `collection_group` sem `order_by` combinado**
- Mesma disciplina já estabelecida em `domains/admin/repository.py::
  list_access_requests`: evita depender de índice composto/de
  collection-group manual no Firestore (que falharia silenciosamente em
  produção sem esse índice existir) — ordenação e agrupamento sempre em
  Python.

### Status até o momento
- Backend: 545 testes unitários, 100% passando, `ruff check`/
  `ruff format --check` sem erros.
- Frontend: `tsc --noEmit` limpo, `pnpm lint` (biome) sem erros,
  `pnpm build` concluído.
- Validação visual (gráficos, drill-down, KPIs) fica a cargo do usuário
  após deploy em dev — sem ferramenta de browser neste ambiente.

---

## 4 ajustes de UX: busca no menu, contraste, voltar no admin, favoritos por dataset/apelido

Branch `feat/sprint-3.2`. Usuário validou a reorganização da sidebar por
serviço e o admin em uso real e voltou com 4 pedidos, em ordem de
prioridade declarada.

### O que foi feito

1. **"Buscar tabelas" dentro de "Datasets disponíveis"** — era um link
   solto acima das seções da sidebar; movido pra dentro da seção, como
   primeiro item.
2. **Contraste de `--muted-foreground` corrigido** — `#5b626c` sobre
   `#1d1d1b` media ~2.74:1 (WCAG AA exige ≥4.5:1 pra texto normal),
   calculado via fórmula de luminância relativa (sRGB → linear →
   contraste), não só "parecia ruim". Trocado por `#8f96a1` (mesma
   família azul-acinzentada, 5.66:1 contra `--background`, 4.82:1
   contra `--card`, fundo real da sidebar). Atualizado em `index.css`
   **e** em `docs/skills/frontend.md` juntos — a skill é a fonte de
   verdade documentada da paleta dp6 e precisa ficar sincronizada.
3. **Botão de voltar no `/admin`** — primeira tela do app com esse
   padrão; link discreto (`ArrowLeft` + "Voltar") pra `/`.
4. **Favoritos com dois níveis (tabela/dataset) + apelido** — reescrita
   do domínio `favorites`: `FavoriteTable` virou `Favorite`
   (`table_id: str | None`, `None` = favorito do dataset inteiro) e
   ganhou `nickname: str | None`. Nova rota
   `DELETE /favorites/{project_id}/{dataset_id}` (nível dataset,
   coexiste com a de nível tabela por diferença de segmentos de path).
   Estrela de favoritar dataset adicionada em duas navegações novas: a
   lista "Datasets disponíveis" da sidebar e o cabeçalho de
   `CatalogDatasetPage.tsx`. Seção "Favoritos" da sidebar dividida em
   "Tabelas favoritas" / "Datasets favoritos". Apelido editável inline
   (lápis no hover → input, sem dialog) via `FavoriteNickname.tsx`.

### Decisões desta sessão

**Decisão 1 — `added_at` e `nickname` preservados em upsert repetido**
- Mesmo racional já usado em `domains/admin/repository.py::upsert_user`
  pra `created_at`: sem preservar `added_at`, editar só o apelido de um
  favorito existente reordenaria a lista (ordenada por `added_at`
  desc) — efeito colateral indesejado de uma ação que devia ser só
  renomear. `nickname` ganhou semântica de três estados na chamada de
  `add_favorite`, não dois: `None` = não mexe no apelido já salvo
  (o toggle de favoritar/desfavoritar nunca passa `nickname`, e não
  pode apagar um apelido existente sem querer); `""` = remove o
  apelido de propósito; qualquer outra string = define o apelido.

**Decisão 2 — Contraste corrigido com medição, não só percepção**
- Perguntado e confirmado com o usuário: atualizar `index.css` e
  `docs/skills/frontend.md` juntos. O valor novo foi calculado (não
  escolhido a olho) pra garantir ≥4.5:1 contra os fundos reais onde o
  token aparece.

**Decisão 3 — Apelido editado inline, sem dialog**
- Perguntado e confirmado com o usuário: lápis aparece no hover do
  item (`group-hover`), clique troca o texto por um `Input` autofocado
  ali mesmo — consistente com a preferência por menos fricção nessa
  interação específica (diferente do padrão de dialog já usado em
  `AdminUsersTab.tsx`, mantido lá por ser uma edição com mais campos).

### Status até o momento
- Backend: 534 testes unitários, 100% passando, `ruff check`/`ruff
  format --check` sem erros.
- Frontend: `tsc --noEmit` limpo, `pnpm lint` (biome) sem erros,
  `pnpm build` concluído.
- Validação visual (legibilidade do contraste, favoritos de dataset,
  apelido inline, botão voltar) fica a cargo do usuário após o deploy
  — sem ferramenta de browser neste ambiente.

---

## Admin v1.1: projetos públicos, visão por projeto, solicitação de acesso, mensagens de erro

Branch `feat/finops-budget`. Extensão do ACL v1.0 (ADR-009) — usuário
testou em produção e voltou com três pedidos.

### O que foi feito

1. **Mensagens de erro visíveis** — `ProjectSelector.tsx` mostrava "sem
   acesso" só como um ícone com tooltip no hover. Trocado por um painel
   flutuante (`ApiErrorNotice`, mesmo componente usado no resto do app,
   que ganhou uma prop `action` opcional) com o texto completo e, quando
   o erro é `project_not_authorized`, um botão "Solicitar acesso".
2. **Visão por projeto + projeto público** — nova coleção Firestore
   `hub_projects/{project_id}` (`is_public`), eixo independente do
   `allowed_projects` de cada usuário — libera geral, inclusive quem
   ainda não tem cadastro no Hub. Nova aba "Por projeto" em `/admin`
   (visão inversa da aba "Por usuário": escolhe um projeto, vê/gerencia
   quem tem acesso), via `array_contains_any` no Firestore.
3. **Solicitação de acesso self-service** — `POST /api/v1/access-requests`
   (fora de `/admin`, qualquer usuário autenticado pede pra si mesmo),
   nova aba "Solicitações" em `/admin` com aprovar/negar, badge de
   contagem no ícone de admin do Topbar (`refetchInterval` de 60s, sem
   WebSocket).

### Decisões desta sessão

**Decisão 1 — Badge discreto no Topbar, não banner intrusivo**
- Perguntado e confirmado com o usuário: aviso de pendências como
  contador no ícone de admin já existente, não uma faixa que aparece
  toda vez que um admin abre qualquer página.

**Decisão 2 — `hub_projects` como conceito novo, não widening do wildcard**
- Perguntado e confirmado: "liberado a todos" é uma coleção própria por
  projeto, checada antes do usuário em `has_project_access` — cobre
  "usuários futuros" de verdade (a checagem roda no momento do acesso,
  não fica gravada na lista de cada usuário no momento da liberação).

**Decisão 3 — Filtro de índice composto do Firestore evitado por design**
- `list_access_requests`/`has_pending_request` foram desenhadas pra usar
  no máximo um campo de igualdade no `.where()` — Firestore exige índice
  composto manual pra combinar múltiplos filtros/order_by em campos
  diferentes, e isso falharia silenciosamente em produção sem esse
  índice existir. Ordenação e filtros extras rodam em Python sobre o
  resultado (coleções pequenas o bastante pra isso não pesar).

**Decisão 4 — Revogar acesso explícito não desliga `is_public`**
- Eixos deliberadamente independentes: `DELETE .../projects/{id}/users/{email}`
  só mexe na lista do usuário. Se o projeto está público, ele continua
  acessível por esse caminho — documentado explicitamente pra não virar
  confusão futura ("removi o acesso mas a pessoa ainda entra").

### Status até o momento
- Backend: 522 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Validação end-to-end (badge de pendentes, aprovar/negar, projeto
  público liberando usuário sem cadastro) fica a cargo do usuário depois
  do deploy — sem ferramenta de browser neste ambiente

---

## Controle de acesso por usuário × projeto + tela de admin (novo, ADR-009)

Branch `feat/finops-budget`. Fora do roadmap de observabilidade
(`docs/prd.md`) — mudança de plataforma/segurança, motivada pelo usuário
ao perceber que o Hub, ao ser vinculado a múltiplos projetos-cliente,
não tinha nenhuma barreira impedindo um usuário autenticado de digitar
o `project_id` de um cliente que não é o dele e ver os dados.

### O que foi feito

Segunda camada de autorização em cima do login (Google OAuth) existente:
- Novo domínio `domains/admin/` (Firestore, coleção `hub_users/{email}`)
  com `is_admin`/`allowed_projects` (aceita wildcard `"*"`).
- `core/auth.py::require_project_access` substitui `get_current_user`
  como gate de router em todo endpoint com `project_id` no path
  (catalog, freshness, profiling, quality, lineage, pii, access,
  finops, projects — 9 routers, uma linha cada) — nega antes de
  qualquer chamada real ao BigQuery/Cloud Logging, mesmo que a SA de
  runtime tenha IAM no projeto.
- `core/auth.py::require_admin` gateia a tela `/admin` nova
  (`features/admin/AdminPage.tsx`) — CRUD de usuários administrados,
  sem senha nova, sem Cloud Run novo, reaproveitando 100% da sessão
  OAuth já existente. Link condicional no Topbar (`ShieldCheck`), só
  visível pra quem `is_admin`.
- `scripts/seed_admin.py` novo — bootstrap do primeiro admin (problema
  de ovo-e-galinha: `hub_users` vazio bloqueia `/admin` pra todo mundo,
  ninguém consegue criar o primeiro registro pela UI).
- Spec completa em `docs/specs/admin.md`, decisão arquitetural em
  `docs/adr/ADR-009-acl-usuario-projeto.md` (complementa ADR-006, não
  substitui).

### Decisões desta sessão

**Decisão 1 — Firestore, não Secret Manager, pro ACL**
- A SA de runtime já lê/escreve Firestore hoje (favoritos, histórico) —
  zero IAM novo. Secret Manager é versionado/imutável por natureza,
  inadequado pra CRUD via UI; e o `@lru_cache` sem TTL de
  `get_oauth_allowlist` (Secret Manager) já causou staleness real nesta
  mesma sessão. Leitura de ACL é sempre fresca, sem cache, de propósito.

**Decisão 2 — Login (OAUTH_ALLOWLIST) continua como está, mas sem dar
acesso implícito a projeto**
- Perguntado explicitamente ao usuário se o allow-por-domínio do login
  deveria ser removido (exigindo cadastro individual de todo mundo,
  inclusive time interno) ou mantido só pra login, sem acesso a projeto
  por padrão. Escolhida a segunda opção — menos risco de lockout no dia
  do deploy, mesmo nível de segurança de projeto (quem só passa pelo
  domínio ainda precisa de liberação explícita de um admin pra ver
  qualquer `project_id`).

**Decisão 3 — Wildcard `"*"` em vez de lista exaustiva pra acesso total**
- Perguntado e confirmado com o usuário — admins/líderes que precisam
  ver todos os projetos-cliente usam `"*"` em vez de listar cada um.
  Menos auditável que lista exaustiva, mas muito mais fácil de manter;
  aceito conscientemente.

**Decisão 4 — `is_admin` só populado em `GET /auth/me`, nunca em
`get_current_user`**
- `get_current_user` roda em todo request autenticado — não ganha I/O
  novo (uma leitura Firestore a mais em toda chamada de
  catalog/freshness/etc. seria desperdício). Consequência: `is_admin`
  só é confiável quando `UserInfo` vem de `/auth/me`; `require_admin`
  nunca confia nesse campo, sempre faz checagem fresca própria.

**Decisão 5 — Bloqueio de remover o último admin**
- `upsert_user`/`delete_user` recusam (`LastAdminLockoutError`, 400)
  remover `is_admin` do último administrador restante — sem isso, um
  erro de operação zeraria os admins e ninguém mais conseguiria abrir
  `/admin` pra reverter.

### Investigação técnica relevante

Antes de trocar a dependency de 9 routers, confirmado lendo o código
instalado do FastAPI (`0.141.1`) que uma dependency declarada a nível
de `APIRouter(dependencies=[Depends(fn)])` resolve path params (ex:
`project_id`) da mesma forma que uma dependency de endpoint — o `path`
usado na resolução é o da rota real (prefixo + path), não um path
genérico do router. Isso permitiu trocar `get_current_user` por
`require_project_access` com uma linha por router, sem tocar em nenhum
endpoint individual.

### Status até o momento
- Backend: 492 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Validação end-to-end (login real, `/admin` funcionando, 403 num
  projeto sem ACL) depende do bootstrap do primeiro admin em dev —
  fica a cargo do usuário depois do deploy (sem ferramenta de browser
  neste ambiente)

---

## Reorganização de navegação: hierarquia por serviço observável

Branch `feat/finops-budget`. Não é uma fase nova — mudança estrutural na
sidebar pedida pelo usuário, preparando o Hub pra observar outros
serviços GCP além de BigQuery no futuro (hoje é o único).

### O que foi feito

`DatasetSidebar.tsx` reestruturada em dois níveis: um nó de topo por
serviço observável (`SidebarServiceGroup` — ícone + label + chevron,
visualmente mais forte que as subseções) contendo tudo que já existia
(Buscar tabelas, Governança, FinOps, Datasets disponíveis, Favoritos,
Recentes) como `SidebarSection`s dentro dele. "Governança" e "FinOps"
eram headers estáticos (`<p>`), viraram seções recolhíveis de verdade —
única mudança de comportamento em cima do que já existia, além do
aninhamento.

**Estado inicial:** o grupo "BigQuery" abre por padrão (é o único
serviço hoje — começar fechado deixaria a sidebar vazia no primeiro
acesso); todas as subseções de dentro começam **recolhidas**, sem
exceção (inclusive Datasets disponíveis, que antes abria por padrão) —
decisão explícita do usuário, confirmada via pergunta direta sobre o
estado do nó de topo antes de implementar.

Próximo serviço observável (quando existir) vira um `SidebarServiceGroup`
irmão do de BigQuery, mesmo componente reaproveitado.

### Status
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Sem mudança de backend/API — só reorganização de UI
- Validação visual em browser não feita nesta sessão (sem ferramenta de
  browser disponível no ambiente) — pendente de validação do usuário

---

## Fase 4 — FinOps: sugestão de tipo de coluna (concluída, 1ª parte da 3ª frente)

Branch `feat/finops-budget` (mesma branch da 2ª frente, budget — ainda sem
PR pra `main`). Primeira metade de "otimizações sugeridas"
(`docs/prd.md`, 4.3) — a segunda metade (clustering) foi deliberadamente
deferida, ver "Decisão 1" abaixo.

### O que foi feito

Terceira aba em `/finops` ("Tipos de coluna"): detecta colunas `STRING`
cujos valores amostrados são compatíveis com um tipo mais estreito
(`INT64`, `FLOAT64`, `BOOL`, `DATE`, `DATETIME`, `TIMESTAMP`), com
estimativa de economia de storage mensal. Novo par de endpoints —
`POST /finops/{project}/column-type-suggestions/estimate` (dry-run
gratuito) e `.../run` (execução real) — projeto inteiro, não por tabela.

### Decisões desta sessão

**Decisão 1 — Onde a feature mora: nova aba no scanner de desperdício
(projeto inteiro), não no modal de profiling**
- Diferente do scanner de desperdício e do budget (100% metadado/audit
  log, custo $0), esta feature precisa amostrar dado real via
  `TABLESAMPLE` — mesmo custo real que `pii`/`quality` já têm. Perguntado
  explicitamente ao usuário se a feature deveria viver como aba nova no
  scanner de desperdício (visão de projeto inteiro) ou como aba nova no
  modal de profiling (por tabela, mesmo lugar de PII) — escolhido o
  scanner de desperdício. Consequência: fluxo em duas etapas (dry-run
  "Estimar custo" antes de "Escanear", nunca automático ao abrir a tela)
  pra nunca cobrar do usuário sem ele decidir antes olhando pro número.

**Decisão 2 — Nunca sugerir sem economia real, nem com confiança parcial**
- Só vira sugestão se (a) 100% dos valores não-nulos **amostrados**
  batem no tipo candidato (não um limiar configurável tipo "a maioria" —
  aplicar um tipo mais estreito numa coluna que não converte 100%
  quebraria dado real) e (b) a troca de fato economiza bytes
  (`avg_current_bytes > bytes fixos do tipo sugerido` — uma `STRING`
  curta como `"1"` já ocupa menos espaço que um `INT64` de 8 bytes fixos,
  então sugerir a troca nesse caso pioraria o storage). Mesma disciplina
  de "nunca superestimar economia" já aplicada ao scanner de
  particionamento (Fase 4, 1ª frente).

**Decisão 3 — Clustering deferido, não faz parte desta v1**
- Diferente de tipo de coluna (comparação de bytes é objetiva e
  determinística), sugerir clustering exigiria inferir quais colunas
  aparecem com mais frequência em `WHERE`/`GROUP BY`/`JOIN` — só
  disponível via texto livre de query nos audit logs, sem um parser de
  SQL de verdade isso vira heurística de regex frágil. Documentado como
  "fora do escopo" em `docs/specs/finops-column-types.md`, não
  esquecido — merece spec e conversa própria sobre nível de confiança
  aceitável antes de implementar.

**Decisão 4 — Orçamento de tempo por lote, não por tabela**
- `/run` escaneia todas as tabelas elegíveis do projeto em paralelo
  (`ThreadPoolExecutor`, `max_workers=4` — mais conservador que os
  `max_workers=8` de operações gratuitas do domínio, porque aqui cada
  query tem custo real). Orçamento total de 120s pro lote inteiro; se
  esgotar no meio, retorna as tabelas já escaneadas com um `warning` de
  resultado parcial em vez de lançar erro — parcial ainda tem valor aqui
  (lista de oportunidades), diferente de um scan de tabela única em
  `pii`/`quality`, onde parcial não faz sentido.

### Correções pós-validação em dev (mesma branch, v1.1 da spec)

Usuário validou a v1.0 em dev e voltou com dois pedidos, ambos
implementados na mesma sessão:

**1 — Escopo de execução (obrigatório pra produção)**
- Rodar em todas as tabelas de um projeto real é inviável — a v1.0
  fazia isso por padrão. `ColumnTypeScanRequest` ganhou `tables:
  list[str] | None` (`"dataset_id.table_id"`); com escopo explícito,
  `_resolve_eligible_tables` **pula** `repository.list_all_table_refs`
  inteiramente (não enumera o projeto todo só pra filtrar depois).
  Frontend: novo `ColumnTypeScopePicker` (checkbox por dataset — marca
  todas as tabelas dele — que expande em checkboxes por tabela pra
  refinar), com `useDatasets`/`useTables` do catálogo reaproveitados
  (nenhum endpoint novo pra listar datasets/tabelas). Botões
  "Estimar custo"/"Escanear" desabilitados até haver seleção — decisão
  deliberada de não default pra "projeto inteiro" nunca aparecer como
  opção fácil na UI, mesmo a API aceitando `tables=None` por
  flexibilidade/testes.
- Novo componente `components/ui/checkbox.tsx`, adicionado via
  `npx shadcn add checkbox` (primeira vez que esse primitive é usado no
  Hub).

**2 — Também disponível por tabela, dentro do modal de profiling**
- Nova aba "Tipos de coluna" em `ProfilingDialog.tsx`, ao lado de
  Schema/Análise/Histórico/Lineage/PII/Acesso — mesmo padrão de
  `PiiTab.tsx`, mas chamando os mesmos endpoints de projeto com escopo
  implícito de uma tabela só (`tables: ["{dataset}.{tabela}"]`). Sem
  seletor aqui — não faz sentido escolher escopo quando o modal já é
  sobre uma tabela específica.
- Extraído `ColumnTypeSuggestionBadges` (badges de sugestão) como
  componente compartilhado entre a aba de projeto e a aba do modal, pra
  não duplicar a lógica de exibição.

### Status até o momento
- Backend: 468 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Ainda não validado em dev nesta rodada (v1.1) — v1.0 já tinha sido
  validada
- Falta: sugestão de clustering (deferida, ver Decisão 3) — depois disso
  a Fase 4 fecha

---

## Fase 4 — FinOps: budget de custo (em andamento, 2ª de 3 frentes)

Branch `feat/finops-budget`, criada a partir de `feat/finops-waste-scanner`
(PR #19 do scanner de desperdício ainda não mergeado — mesma decisão de
não bloquear a próxima frente esperando review, já usada entre
sprint-3.2 e o scanner).

### O que foi feito

Quatro visões de custo do mês corrente em `GET /api/v1/finops/{project}/budget`,
todas derivadas dos **mesmos audit logs** que o scanner de desperdício já
lê — nenhuma integração nova, nenhuma role de IAM nova:
- **Custo por dataset**: soma `totalBilledBytes` de todo job que
  referenciou uma tabela daquele dataset no mês.
- **Top N queries mais caras**: job_id, quem rodou, tabelas tocadas,
  texto da query (truncado em 2000 caracteres), ordenadas por custo.
- **Top N gastadores**: humano vs. service account, custo total,
  contagem de jobs.
- **Projeção do mês**: custo até agora ÷ dias corridos do mês × dias no
  mês.

Nova página `/finops/budget`, com stat cards de projeção + três tabelas
(reaproveitando `useTableFilterSort`, mesmo hook do scanner de
desperdício). Sidebar ganhou uma segunda entrada no grupo FinOps.

### Erros e decisões desta sessão

**Decisão 1 — Descartada a ideia de usar BigQuery Billing Export**
- Cogitado inicialmente (e chegou a ser mencionado errado numa resposta
  pro usuário) que essa frente precisaria de uma fonte de dados nova
  (Cloud Billing Export ou API). Corrigido antes de implementar: Billing
  Export só quebra custo por **projeto + SKU**, nunca por dataset —
  não resolveria a pergunta que esta feature responde, mesmo se
  configurado. A granularidade certa só existe nos audit logs de job
  (mesma fonte já integrada), então nada precisou ser configurado a
  mais no projeto do cliente.
- Reforça a mesma premissa já embutida em `domains/quality` e no
  scanner de desperdício: a estimativa é on-demand (bytes escaneados ×
  preço/TiB) — não reflete gasto real em projetos com preço flat-rate/
  Editions. Documentado explicitamente em `docs/specs/finops-budget.md`
  por ser o lugar onde um número errado mais provavelmente vira decisão
  financeira.

**Decisão 2 — SA do próprio Hub CONTA aqui, diferente do mapa de acesso**
- `domains/access` exclui a SA de runtime do Hub porque ali a pergunta é
  "quem consome essa tabela de fora" (inspecionar pelo Hub não é
  consumo externo real). Budget pergunta outra coisa — "quanto está
  sendo gasto de verdade" — e profiling/PII rodados pela UI custam
  dinheiro real, então devem contar. Nenhuma exclusão aplicada aqui,
  documentado o contraste explicitamente pra não parecer inconsistência
  acidental entre os dois domínios.

**Decisão 3 — `ScanEvent` estendido em vez de mais um parser duplicado**
- `job_id`/`principal_email`/`query_text` foram adicionados ao mesmo
  `ScanEvent` que o scanner de desperdício já usa (com default vazio,
  no fim da dataclass, pra não quebrar as chamadas existentes) em vez
  de criar uma quarta cópia quase idêntica do parsing de audit log —
  as duas funcionalidades do domínio finops compartilham o mesmo
  repository.py.

### Correções e melhorias pós-review (mesma branch, v1.1 da spec)

Ticket do usuário reportando dois bugs e duas melhorias na tela de
budget. Ver `docs/specs/finops-budget.md` (v1.1) para o detalhe completo.

**Bug real encontrado durante a investigação — regiões fantasma**
- O ticket original descrevia a causa como "busca custo em todas as
  regiões do `BQ_REGIONS` via `INFORMATION_SCHEMA.JOBS`" — verificado
  via grep que isso é **factualmente incorreto**: `get_budget()` nunca
  iterou regiões nem leu `INFORMATION_SCHEMA.JOBS`, só Cloud Logging.
  Perguntado ao usuário se o sintoma ($0.07 fantasma) era real ou
  hipotético antes de implementar o fix descrito — confirmado real.
- Causa raiz investigada com `gcloud logging read` (5000 eventos reais
  de agosto/2026 em `observability-hub-dev`) + replay da lógica de
  agregação: `discover_regions()`/`list_all_table_refs()`/
  `get_date_like_columns()` (usadas por catalog/freshness/finops para
  descoberta de metadados a custo ~zero) rodam
  `` `project.region-X.INFORMATION_SCHEMA.*` `` — o audit log dessas
  queries tem `datasetId="region-US"` e `tableId="INFORMATION_SCHEMA.*"`,
  contado como se fosse um dataset real. **4989 de 5000 jobs amostrados
  (99,8%) eram esse ruído.**
- Fix: `repository._parse_table_ref()` descarta `table_id` que comece
  com `INFORMATION_SCHEMA.` na origem (beneficia todas as funções do
  domínio); `get_budget()` pula o evento inteiro quando não sobra
  nenhuma tabela real do projeto após o filtro.

**Bug 2 — sobreposição visual em "queries mais caras"**
- Texto da query inline na célula colidia visualmente com a coluna de
  tabelas. Fix: texto oculto por padrão, toggle "Ver query"/"Ocultar
  query" por linha expande um bloco `SqlPreview` (componente já
  compartilhado com o preview de SQL do profiling) abaixo da linha.

**Melhoria 1 — agrupamento configurável**
- `by_dataset`/`top_spenders` (visões fixas da v1.0) substituídos por
  `groups: CostGroup[]` + `group_by: table|user|day|month|year`. O
  ticket original descrevia isso via `GROUP BY` em SQL sobre
  `INFORMATION_SCHEMA.JOBS` — reimplementado sobre a arquitetura real
  do domínio (Cloud Logging, sem query BQ nova, sem custo/IAM
  adicional): `service._group_keys()` deriva a chave a partir do
  `ScanEvent` já em memória.

**Melhoria 2 — layout em duas abas**
- `BudgetPage.tsx` reescrita: seções empilhadas → `Tabs` do shadcn/ui
  ("Custo por agrupamento" com pill buttons de `group_by` + total no
  rodapé via `TableFooter`; "Queries mais caras" com o toggle do Bug 2).

### Status até o momento
- Backend: 431 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Commitado na branch `feat/finops-budget`, push e PR **não** feitos —
  aguardando validação manual em dev e aprovação do usuário
- Falta a 3ª frente de FinOps (otimizações sugeridas) e a lacuna da v1
  do PII (adiada, não esquecida)

---

## Fase 4 — FinOps: scanner de desperdício (concluída, PR #19)

Branch `feat/finops-waste-scanner`, criada a partir de `feat/sprint-3.2`
(PR #18 da Sprint 3.2 ainda não mergeado em `main` no momento desta
sessão — decisão consciente do usuário pra não bloquear o início da
Fase 4 esperando review). Primeira das três frentes do roadmap de
FinOps (`docs/prd.md`): scanner de desperdício. Budget/custo por
dataset e otimizações sugeridas ficam pra sessões futuras — a lacuna da
v1 do PII (detecção de nome de pessoa, classificação de sensibilidade
por tabela) foi explicitamente adiada, não faz parte deste trabalho.

### O que foi feito

**Novo domínio `domains/finops`** — duas checagens independentes:

1. **Tabelas sem uso** (`GET /finops/{project}/unused-tables?min_days_unused=30|60|90`):
   tabelas sem leitura conhecida nos audit logs, com custo de storage
   evitável estimado via `size_bytes × preço/GB` (BigQuery já rebaixa
   pra tarifa long-term sozinho depois de 90 dias sem modificação — a
   estimativa usa a tarifa certa conforme `last_modified_time`, não uma
   única tarifa fixa).
2. **Candidatas a particionamento** (`GET /finops/{project}/partition-candidates`):
   tabelas grandes (≥1GB), sem partição, com coluna
   `DATE`/`DATETIME`/`TIMESTAMP` candidata. Estimativa de economia
   **ancorada em custo real observado** (`jobStatistics.totalBilledBytes`
   dos audit logs, campo que nenhum outro domínio lia ainda) em vez de
   uma suposição do zero — só aparece quando há custo real na janela de
   30 dias, sempre como faixa (30%–70% de redução), nunca um número
   único, com disclaimer explícito. Ver "Decisão 1" abaixo — foi uma
   escolha de design discutida em detalhe com o usuário antes de
   implementar, pra não gerar frustração com uma economia superestimada.

Nova página de frontend `/finops` (fora do modal de profiling, diferente
de PII/lineage/access — é uma visão de projeto inteiro, não de uma
tabela só, mesmo padrão de `/orphans`), duas abas (Tabelas sem uso /
Candidatas a particionamento), link novo no sidebar.

### Erros e decisões desta sessão

**Decisão 1 — Estimativa de economia de particionamento: nunca fabricar
um número de aparência precisa sobre suposição não verificada**
- Pedido inicial era "estimativa heurística aproximada". Discutido com o
  usuário até chegar num desenho que ancora a base em dado real (custo
  de scan já observado nos audit logs, não uma frequência de query
  assumida) e só extrapola daí — e mesmo assim como faixa, não um valor
  único, com o disclaimer sempre visível. Justificativa do usuário:
  "sem superestimar a economia para não gerar frustração" — um número
  de decisão financeira errado é pior que não mostrar número nenhum.
- Limitação assumida e documentada: se a query faz `JOIN` com outra
  tabela grande, o custo mostrado é da query inteira, não isolado só
  daquela tabela — sem tentativa de dividir a proporção, dado que não
  está disponível no audit log.

**Decisão 2 — Reaproveitar `core/bigquery.py::get_tables_metadata` em
vez de duplicar mais uma vez**
- Diferente de lineage/pii/access (que duplicam parsing de audit log
  entre si, por serem domínios distintos), a enumeração de tabelas com
  tamanho/partição/`last_modified_time` já vive em `core/bigquery.py`
  (`get_table_cached`/`get_tables_metadata`, usado por catalog e
  freshness) — reaproveitada direto aqui, sem duplicar, porque é
  infraestrutura compartilhada (`core/`), não código de outro domínio.
  A regra de "domínios não importam um do outro" nunca foi sobre
  proibir reaproveitar `core/`.
- `domains/finops/repository.py` ainda duplica o parsing de audit log
  em si (terceira vez, depois de lineage e access) — o que muda é o
  campo novo extraído (`jobStatistics.totalBilledBytes`) e que não
  precisa de `destination_table`/`principal_email`, só leitura.

### Status até o momento
- Backend: 411 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc -b`, `vite build` limpos
- Validado em dev pelo usuário — incluindo dois bugs pegos e corrigidos
  ao vivo depois do deploy: `min_days_unused` como `Literal[int,...]`
  causando 422 (trocado por `IntEnum`) e retry do TanStack Query
  insuficiente pra sobreviver ao cold start do Cloud Run em dev
  (`minScale=0`, decisão consciente do usuário de não mudar).
- Aproveitado o momento pra reorganizar o sidebar em grupos e adicionar
  filtro/ordenação reutilizável (`hooks/useTableFilterSort`) nas tabelas
  de "Tabelas sem consumidor" e do próprio scanner.
- **PR #19 aberto** (`feat/finops-waste-scanner` → `main`, diff limpo
  contra `main` já com a Sprint 3.2 mergeada).
- Faltam a 3ª frente de FinOps (otimizações sugeridas) e a lacuna da v1
  do PII (adiada, não esquecida)

---

## Sprint 3.2 — Qualidade, Discovery e melhorias de UX em tabelas (concluída)

Branch `feat/sprint-3.2`, a partir de `main` pós-PR #17. Sete itens
planejados; sete implementados e testados nesta sessão (o item de score
de qualidade foi implementado, validado e depois removido por completo a
pedido do usuário — por isso a numeração abaixo chega a 6 novas
features, não 7).

### O que foi feito
1. **Filtros e ordenação client-side**: busca por nome + filtro por tipo/
   status SLA + colunas ordenáveis, sem mudança de backend, em
   `AssetsTable` (catálogo), `TableFreshnessTable` (tabelas de um
   dataset) e `DatasetFreshnessTable` (datasets de um projeto, adicionado
   depois a pedido do usuário). Componente `SortableTableHead`
   compartilhado, promovido de um componente que só existia na busca.
2. **Score de qualidade por tabela — implementado e revertido**: média
   ponderada de completude/freshness/duplicatas/documentação (0-100),
   persistida em Firestore por profiling, badge na tabela de ativos.
   Validado em dev e então removido por completo por decisão do usuário.
3. **Histórico de qualidade**: cada profiling grava um snapshot em
   Firestore (máximo 30 runs por tabela); aba "Histórico" no modal com
   gráfico de linha (`recharts`), tabela de runs expansível por coluna e
   alerta de degradação (>10pp de queda de densidade vs. run anterior).
4. **Lineage e tabelas órfãs**: novo domínio a partir de audit logs de
   BigQuery (Cloud Logging) — upstream/downstream de uma tabela e lista
   de órfãs (sem consumidor conhecido). Limitação de visibilidade tratada
   com honestidade: resultado vazio vem com aviso explicando que pode ser
   falta de atividade OU audit logs desabilitados (indistinguível via
   API), em vez de afirmar uma certeza que a implementação não tem.
   **Evoluído na mesma sessão para v2** (spec `docs/specs/lineage.md`):
   upstream/downstream deixou de ser 1 hop direto e virou cadeia
   transitiva completa (ex: `daily_summary` ← `ga4_sessions` ←
   `ga4_events`), representada como grafo dirigido (BFS bidirecional em
   `domains/lineage/service.py`, `max_hops` configurável, padrão 8),
   atravessando projetos GCP quando necessário (nó vira "acesso negado"
   em vez de derrubar a requisição se a SA não tiver Logging no projeto
   não-raiz). Frontend passou de duas listas planas para um diagrama
   (`LineageGraph.tsx`, `@xyflow/react` + `dagre` para layout), sempre
   com o prefixo `project.dataset.table`. Validado em dev pelo usuário
   após o deploy — cadeia completa (`ga4_events → ga4_sessions →
   daily_summary`) confirmada contra audit logs reais.
5. **Fingerprinting de PII**: novo domínio `domains/pii`, nova aba "PII"
   no mesmo modal de profiling (`ProfilingDialog.tsx`). Duas camadas:
   heurística de nome de coluna (grátis, `INFORMATION_SCHEMA.COLUMNS`) +
   amostragem real via `TABLESAMPLE SYSTEM` com `REGEXP_CONTAINS`/
   `COUNTIF` por coluna (email, CPF, CNPJ, telefone BR, CEP, cartão de
   crédito — conjunto BR completo, a pedido do usuário). Coluna só é
   sinalizada pela amostra se ≥ `match_threshold_pct` (padrão 5%) dos
   valores não-nulos amostrados baterem no regex, não "qualquer match" —
   reduz falso positivo de coincidência isolada. Mesmo padrão de
   `/estimate`+`/run` (dry-run antes de executar) e cache de 5min do
   domínio `quality`, reaproveitados ao máximo. Matching roda inteiramente
   em SQL dentro do BigQuery — a API nunca recebe nem loga um valor de
   coluna real, só contagens agregadas. Validado em dev pelo usuário.
6. **Mapa de acesso**: novo domínio `domains/access`, nova aba "Acesso"
   no mesmo modal de profiling. Reaproveita a mesma fonte de dados do
   lineage (audit logs de jobs BigQuery via Cloud Logging), sob um
   ângulo diferente — "quem tocou nessa tabela" em vez de "de onde vem/
   pra onde vai o dado". Agrega por `principal_email`: último acesso,
   contagem, tipo (leitura/escrita) e se é usuário humano ou service
   account (heurística: email termina em `gserviceaccount.com`).
   Diferente do lineage, uma auto-referência (ex: MERGE lendo e
   escrevendo a própria tabela) **conta** como acesso real, em vez de
   ser excluída — ali representaria um ciclo sem sentido, aqui é
   exatamente o tipo de evento que o mapa de acesso quer mostrar.
   Endpoint único (`GET /{project}/{dataset}/{table}`, sem custo de BQ,
   só Cloud Logging), sem fluxo estimar→rodar como PII/profiling — só
   carrega ao abrir a aba, como o Lineage. Fecha os 7 de 7 itens
   planejados da sprint.

### Erros e decisões desta sessão

**Decisão 1 — Score de qualidade removido depois de validado**
- O usuário pediu a remoção completa (backend + frontend) do score de
  qualidade depois de já ter validado a feature em dev, sem registrar o
  motivo. Revertido preservando `core/sla.py` (extração de SLA
  compartilhada entre freshness e quality), que é uma refatoração válida
  independente do score — não fazia sentido desfazer só porque a feature
  que motivou a extração saiu.

**Decisão 2 — Lineage implementado mesmo com Data Access audit logs
desabilitados**
- Pré-requisito técnico da fonte de dados (audit logs de BigQuery via
  Cloud Logging) não está habilitado em nenhum ambiente. Decisão
  consciente do usuário: implementar a feature mesmo assim (ela funciona
  corretamente assim que os logs forem habilitados) em vez de bloquear a
  sprint esperando uma mudança de infraestrutura que não é código.
- Limite técnico registrado explicitamente: a API não consegue
  distinguir "sem atividade no período" de "audit logs desabilitados" —
  os dois casos retornam o mesmo resultado vazio. Resolvido com um campo
  de aviso explícito na resposta em vez de fingir certeza.
- O schema do payload dos audit logs (`BigQueryAuditMetadata`/
  `jobChange`) foi implementado a partir da documentação oficial do
  Google, sem poder validar contra um log real — vale revisitar assim
  que os audit logs forem habilitados e o primeiro job aparecer.

**Decisão 3 — Lineage v1→v2 sem endpoint novo, breaking change direto**
- A extensão pra cadeia transitiva trocou `LineageResponse` (upstream/
  downstream flat) por `LineageGraphResponse` (nodes/edges) na mesma
  rota, em vez de versionar a API. Único consumidor da v1 era
  `LineageTab.tsx` — sem clientes externos, sem convenção de
  versionamento de API em nenhum outro domínio do repo, então manter
  compatibilidade retroativa seria custo sem benefício real.
- Bug encontrado e corrigido no meio do caminho: a v1 comparava
  `(dataset_id, table_id)` descartando `project_id`, então uma tabela
  `outro-projeto.RAW.foo` podia colidir por engano com `RAW.foo` do
  projeto consultado. A travessia v2 casa sempre pela tripla completa.

**Decisão 4 — PII diverge do guard de view de quality: pula a query
paga inteiramente, não só o TABLESAMPLE**
- `quality` (profiling), quando a tabela é VIEW/MATERIALIZED VIEW, só
  omite a cláusula `TABLESAMPLE` e roda a query principal sem amostragem
  — aceitável porque profiling é a funcionalidade central do domínio.
  PII é uma checagem complementar; rodar sem amostragem escanearia a
  view inteira (que pode envolver uma query subjacente pesada) sem o
  usuário ter visto uma estimativa de custo antes. Decisão: pular a
  query de amostragem por completo pra view, mantendo só a heurística de
  nome (grátis) — mesmo padrão de dry-run/estimate de quality, mas com
  esse guard adicional.
- Limitação assumida conscientemente e documentada em
  `docs/specs/pii.md`: os padrões regex (CPF, CNPJ, telefone, cartão)
  validam só formato, sem dígito verificador nem algoritmo de Luhn — e
  não cobrem a variante sem formatação (dígitos crus), que teria alto
  risco de falso positivo contra qualquer sequência numérica do tamanho
  certo.

**Decisão 5 — Mapa de acesso: limitação de visibilidade cross-project
discutida e documentada antes de implementar**
- Durante a conversa sobre o que conta como "acesso" (motivada por uma
  pergunta do usuário sobre um job Glue extraindo do BQ pra S3), ficou
  claro que `list_access_events`/`list_job_events` só enxergam jobs que
  **rodaram no projeto da tabela** — um job rodando em outro projeto que
  lê a tabela via referência cross-project não aparece, porque o audit
  log dele vive no projeto onde ele rodou. Mesma classe de limitação já
  documentada em lineage/órfãs, agora também explícita em
  `docs/specs/access.md`, "Fonte de dados" e "Casos de borda" — em vez
  de descobrir isso depois, via um usuário confuso com um número de
  acessos menor que o esperado.
- Decisão de design: diferente de `get_orphans` (que só conta leitura)
  e do lineage (que exclui auto-referência), o mapa de acesso conta
  leitura **e** escrita, e **não** exclui auto-referência — são
  perguntas diferentes ("quem consome" vs. "de onde vem" vs. "quem
  tocou"), cada domínio com a semântica que faz sentido pra ele mesmo
  reaproveitando a mesma fonte de dados.

### Mudanças de arquitetura
- `core/sla.py`: classificação de SLA extraída de `domains/freshness`
  para `core/`, compartilhada com `domains/quality` (mesmo racional do
  `resolve_dataset_region()` na Fase 2B).
- `core/logging_client.py`: client compartilhado do Cloud Logging, mesmo
  padrão de `core/bigquery.py::get_client()` (singleton via `lru_cache`).
- `LoggingAccessDeniedError` (`core/exceptions.py`) + handler em
  `main.py`: mesmo padrão de `ProjectAccessDeniedError` — falta de IAM
  vira 403 com o comando `gcloud` de correção pronto na resposta.
- `@xyflow/react` + `dagre` (frontend): primeira lib de grafo/diagrama do
  projeto (antes só `recharts`, gráficos, não DAG), adicionada
  especificamente pro diagrama de lineage transitivo — nó custom
  (`LineageGraph.tsx`) reaproveita o padrão visual de bloqueado+tooltip
  já estabelecido nos botões de `AssetsTable.tsx` (item 1 desta sprint)
  pra representar tabelas em projeto sem acesso de Logging.
- `components/SqlPreview.tsx`: promovido de `features/quality/` pro
  nível compartilhado — componente já era genérico (`{sql, defaultOpen}`,
  sem lógica de domínio) e passou a ser usado por `quality` e `pii`, mesmo
  racional do `SortableTableHead` promovido no item 1.
- `domains/pii/`: `repository.py` duplica (não importa)
  `get_table_columns`/`is_view`/`dry_run` de `domains/quality/
  repository.py` — mesma decisão de isolamento de domínio já tomada em
  `domains/lineage/repository.py` (CLAUDE.md proíbe um domínio importar
  de outro).
- `domains/access/`: mesma decisão de duplicação, desta vez sobre
  `domains/lineage/repository.py` — `AccessEvent` é quase idêntico a
  `JobEvent` de lineage, mas carrega também `timestamp`
  (`jobStatistics.endTime`), campo que lineage não lê porque não
  precisa de "quando", só de "de onde/pra onde".

### Status até o momento
- Backend: 367 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc -b`, `vite build` limpos (bundle
  ~1.19 MB / gzip 364 kB)
- Validado em dev (`observability-hub-dev`) pelo usuário: filtros/
  ordenação, histórico de qualidade, lineage v2 (cadeia transitiva
  confirmada contra audit logs reais) e PII. Mapa de acesso ainda não
  validado visualmente no momento deste registro.
- **7 de 7 itens concluídos — sprint fechada.** PR pra `main` ainda não
  aberto.

---

## Sprint 3.1 — Auth (Google OAuth) + UX pessoal (concluída, PR #17)

Reconstruída a partir da descrição do PR #17 — o SESSIONLOG não foi
atualizado durante aquela sessão (falha de processo corrigida a partir
desta sprint).

### O que foi feito
1. **Autenticação real**: senha hardcoded do frontend (dívida técnica
   registrada no backlog da Sprint 2) substituída por Google OAuth 2.0 —
   `domains/auth/` no backend (login, callback, sessão via JWT em cookie
   httpOnly de 12h, allowlist por domínio/email no Secret Manager);
   `RequireAuth` no frontend. Todos os routers de dados passaram a exigir
   sessão válida no backend, não só proteção de rota no frontend.
2. **Modal de profiling**: dois bugs de UI corrigidos (colapso de schema
   em dois níveis, scroll horizontal vazando dos controles) e refatorado
   para Tabs (Schema / Análise de qualidade).
3. **Favoritos**: domínio novo, Firestore por usuário, estrela na tabela
   de ativos com toggle otimista.
4. **Histórico de navegação**: domínio novo, duas subcoleções por usuário
   (visualizações de tabela / buscas), seção "Recentes" na sidebar.

### Erros e aprendizados
- Cookie de logout não limpava de fato a sessão (`delete_cookie` do
  Starlette precisa dos mesmos atributos do cookie original pra
  funcionar) — corrigido em fix separado, pós-validação.

### Status final
- 269 testes backend, `ruff`/`biome`/`tsc`/`vite build` limpos
- Validado em dev pelo usuário (login/logout, allowlist, favoritos,
  histórico, modal de profiling)

---

## Sprint 2.2 e 2.3 — Metadados de partição, refresh, busca reversa e UX (concluída)

Sete funcionalidades sobre o MVP de catálogo/freshness (Fase 2 backend +
Sprint 2 frontend, ambas já concluídas), todas na branch
`feature/partition-metadata`, testadas em dev e validadas pelo usuário
antes de qualquer PR para `main`.

### O que foi feito — Sprint 2.2

1. **Metadados de partição na tabela de ativos**: `partition_type`
   (`"event_date (DAY)"`), `min_partition`, `max_partition`,
   `partition_count` em `TableSummary`, buscados em paralelo só para
   tabelas particionadas.
2. **Botão "Ver partições"**: novo endpoint
   `GET .../tables/{table_id}/partitions`, modal com a lista completa de
   partições distintas + contagem de linhas.
3. **Botão de refresh**: `RefreshButton` compartilhado (`RotateCcw`,
   `animate-spin`), páginas de catálogo e freshness, refetch das queries
   TanStack Query da view atual sem navegar nem limpar o projeto
   selecionado.
4. **Busca reversa tabela → datasets**: novo endpoint
   `GET /catalog/{project_id}/search?q=&mode=exact|contains`, agrupando
   `datasets_with_match`/`datasets_without_match` (este último via
   detecção de prefixo/série, não lista todo dataset do projeto).

### O que foi feito — Sprint 2.3

5. Sidebar de datasets sem os indicadores de status SLA (bolinha
   colorida) — só nome + contagem de tabelas/views.
6. Projeto selecionado persistido em `localStorage`, restaurado e
   revalidado automaticamente no carregamento da página; limpa o storage
   e volta pro campo vazio se a revalidação falhar.
7. Terceiro mode de busca, `not_contains` — inverte a lógica (datasets
   onde nenhuma tabela contém o termo) reaproveitando `mode=contains` +
   o universo completo de datasets do projeto. Resultado da busca
   reescrito como tabelas ordenáveis/filtráveis client-side (`Dataset`,
   `Tabela`, `Atualizado em`, `Linhas`) — `row_count` precisou entrar no
   backend (`DatasetWithMatch`), reaproveitando a mesma chamada
   `client.get_table()` já feita para `last_modified_time`.

### Erros cometidos e aprendizados

**Erro 1 — Reversão completa da estratégia de partições logo na primeira
implementação**
- O que aconteceu: a primeira versão de `get_partition_stats()` seguiu a
  instrução original (usar `INFORMATION_SCHEMA.PARTITIONS`, metadado
  gratuito, com fallback N/D para datasets multi-região). Tecnicamente
  correta, mas **inútil na prática**: todos os datasets de dev e prod
  estão em `US`, então o resultado era N/D sempre. Um PR (#14) chegou a
  ser aberto com essa versão e foi fechado pelo usuário sem merge.
- Correção: reimplementada do zero como uma query real (`MIN`/`MAX`/
  `COUNT(DISTINCT)` direto na coluna de partição), com custo real de
  bytes escaneados em vez de metadado gratuito — mitigado com cache TTL
  de 5min por tabela.
- Aprendizado: "tecnicamente correto pela spec" não é o mesmo que "útil
  no ambiente real" — quando 100% dos dados de teste caem no caso
  degradado de uma spec (aqui, multi-região → N/D), vale checar contra o
  ambiente real antes de considerar a implementação pronta, não só
  contra a spec escrita. `INFORMATION_SCHEMA.PARTITIONS` continua sendo
  uma opção válida em datasets de região específica — só não serve como
  única fonte quando todo o ambiente observado é multi-região.

**Erro 2 — "Linhas" pedida numa tabela sem mudar backend**
- O que aconteceu: a spec da Sprint 2.3 pedia uma coluna "Linhas"
  ordenável no resultado da busca, mas também dizia explicitamente "sem
  mudança de backend" — e o endpoint de busca nunca retornou
  `row_count`. Contradição real, não resolvida com suposição.
- Correção: perguntado ao usuário antes de implementar; decidido
  adicionar `row_count` ao backend mesmo assim, reaproveitando a chamada
  `client.get_table()` que já buscava `last_modified_time` (sem query BQ
  extra).
- Aprendizado: quando uma instrução pede um dado que a fonte não tem E
  proíbe a única forma de obtê-lo, é um bloqueio real — vale perguntar
  em vez de escolher silenciosamente um dos dois lados.

### Mudanças de arquitetura
- Nenhuma mudança estrutural — todas as adições seguem os padrões já
  estabelecidos na Fase 2 (paralelismo com `ThreadPoolExecutor`, cache
  TTL em memória por processo, `service.py` orquestra e `repository.py`
  constrói SQL).

### Status final
- 219 testes unitários backend, 100% passando ✅
- `ruff check`/`ruff format`, `biome check`, `tsc -b`, `vite build`
  limpos em cada commit ✅
- Validado com `curl` contra `observability-hub-dev` (dados reais,
  incluindo o cenário GA4 completo de `not_contains`/prefixo) e pelo
  usuário na interface real, em cada uma das 7 funcionalidades ✅
- Renderização visual no browser **não verificada por este assistente**
  em nenhum momento — Chromium headless não roda neste sandbox (mesma
  limitação de sessões anteriores); toda validação visual foi feita
  pelo usuário diretamente em dev

---

## Fase 2 — Backend MVP (concluída)

### O que foi feito
- Domínio Catálogo (Fase 2A): 4 endpoints, `discover_regions()` para descoberta
  automática de região, modelo de acesso cross-project
- Domínio Freshness (Fase 2B): 2 endpoints, classificação de SLA por janelas
  fixas (12h/24h/48h/7d/1m)
- Domínio Profiling/quality (Fase 2C): 3 endpoints, `sql_builder.py` com
  geração dinâmica de SQL por coluna, dry run de custo, amostragem via
  `TABLESAMPLE SYSTEM`, drill-down de distribuição de nulos ao longo do tempo
- 155 testes unitários passando (100%), com mocks — nenhum toca o BigQuery real
- Validado com `curl` contra `observability-hub-dev` ao final de cada uma das
  três sub-fases, antes de cada commit

### Erros cometidos e aprendizados

**Erro 1 — `INFORMATION_SCHEMA.TABLE_PARTITIONS` não existe em multi-região**
- O que aconteceu: a query de tabelas do catálogo fazia `JOIN` com
  `TABLE_PARTITIONS` para obter `partition_column`; deu `404 NotFound` em
  datasets na multi-região `US`.
- Correção: `TABLE_PARTITIONS` nem tem um campo com o *nome* da coluna de
  particionamento (só `partition_id`, o valor da partição) — e não existe em
  `US`/`EU` de qualquer forma. `partition_column` passou a vir de
  `INFORMATION_SCHEMA.COLUMNS.is_partitioning_column`, que funciona em
  qualquer região e já estava sendo consultada para `clustering_columns`.
- Aprendizado: não confiar em nomes de campo documentados ou sugeridos sem
  validar contra o schema real (`SELECT * LIMIT 1` ou introspecção do
  `result().schema`).

**Erro 2 — `last_modified_time` incorreto, repetido em duas specs**
- O que aconteceu: a spec do catálogo referenciava
  `TABLES.last_modified_time` (não existe) e, na correção seguinte,
  `TABLE_STORAGE.last_modified_time` (também não existe). O mesmo erro
  apareceu de novo na spec de freshness, que também usa `TABLE_STORAGE`.
- Correção: `TABLES` não tem nenhum campo de "última alteração" nesta versão
  do BigQuery; o campo real em `TABLE_STORAGE` é `storage_last_modified_time`.
- Aprendizado: todo campo de `INFORMATION_SCHEMA` citado numa spec precisa
  ser confirmado contra o schema real do projeto antes de implementar — esse
  erro específico se repetiu em 3 ocasiões diferentes ao longo da Fase 2.

**Erro 3 — `description` não existe em `INFORMATION_SCHEMA.COLUMNS`**
- O que aconteceu: o endpoint de detalhe de tabela buscava `description`
  direto de `COLUMNS`; `400 Unrecognized name: description`.
- Correção: `description` vem de `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`,
  com `JOIN` em `field_path = column_name` para não duplicar linhas em
  colunas `STRUCT`/`RECORD` aninhadas.
- Aprendizado: mesmo aprendizado do Erro 2.

**Erro 4 — `TABLE_STORAGE` sem dados para as tabelas de `observability-hub-dev`**
- O que aconteceu: freshness e profiling dependem de `TABLE_STORAGE` para
  `last_modified_time`/`total_rows`/`size_bytes`; a view retornou 0 linhas
  para as tabelas do projeto dev durante toda a Fase 2.
- Investigação: `TABLE_STORAGE` exige a opção de projeto
  `enable_info_schema_storage` habilitada por região (via `ALTER PROJECT`) —
  mas essa opção já estava `true` em `observability-hub-dev` (confirmado
  consultando `INFORMATION_SCHEMA.PROJECT_OPTIONS`), então não era o
  bloqueio. O motivo real é o lag de propagação que a documentação do Google
  descreve como "cerca de 1 dia" após habilitar a opção ou após mudanças na
  tabela até os dados de storage aparecerem.
- Correção: todo campo que depende de `TABLE_STORAGE`
  (`last_modified_time`, `size_bytes`, `row_count`, `hours_since_update`,
  `sla_status`) foi tipado como opcional (`| None`) em vez de obrigatório.
- Aprendizado: qualquer domínio que dependa de `TABLE_STORAGE` precisa
  tolerar ausência de dado para tabelas recém-criadas ou recém-modificadas —
  não é bug do nosso código, é o comportamento documentado do BigQuery.

### Mudanças de arquitetura
- `resolve_dataset_region()` movido de `domains/catalog/repository.py` para
  `core/bigquery.py` durante a Fase 2B — passou a ser compartilhado entre
  catalog e freshness (e, na prática, também usado por quality na Fase 2C).
  `catalog/repository.py` reexporta o nome para não quebrar chamadas
  existentes de `service.py` e dos testes. Justificativa: `core/exceptions.py`
  já antecipava essa necessidade desde a Fase 2A ("catalog hoje; freshness e
  profiling depois").

### Status final
- Catálogo: 4 endpoints ✅ | Freshness: 2 endpoints ✅ | Profiling: 3 endpoints ✅
- 155 testes unitários, 100% passando ✅
- `ruff check` + `ruff format` limpos em todas as três sub-fases ✅
- Validado com `curl` contra `observability-hub-dev` (dados reais, incluindo
  multi-região `US`, tabelas particionadas/clusterizadas e profiling
  completo em `RAW.crm_leads`) ✅

---

## Fase 1 — Infraestrutura base (concluída)

### O que foi feito
- Bootstrap do Terraform aplicado manualmente em dev e prod
  - Bucket GCS de remote state por ambiente
  - Workload Identity Federation (GitHub Actions → GCP sem service account keys)
  - Service accounts de deploy com permissões mínimas
- GitHub Actions configurados (5 workflows)
  - `terraform-plan.yml` — roda em todo PR que toca infra/
  - `terraform-apply-dev.yml` — push em qualquer branch exceto main
  - `terraform-apply-prod.yml` — push/merge em main
  - `backend-deploy-dev.yml` — build + push + deploy Cloud Run dev
  - `backend-deploy-prod.yml` — build + push + deploy Cloud Run prod
- Módulo Terraform `cloud-run` criado e aplicado em dev e prod
  - Artifact Registry repository
  - Service account de runtime dedicada (backend-run)
  - Cloud Run com health check em /health e lifecycle.ignore_changes na imagem
- Backend skeleton deployado em dev e prod
  - FastAPI com GET /health → {"status": "ok"}
  - Dockerfile multi-stage, usuário não-root, uv como gerenciador de pacotes

### Erros cometidos e aprendizados

**Erro 1 — Permissão faltando no bootstrap**
- O que aconteceu: `gh-deploy-prod` não tinha `roles/iam.serviceAccountAdmin`,
  apenas `roles/iam.serviceAccountUser`. O Terraform Apply falhou ao tentar
  criar a service account `backend-run` no primeiro deploy.
- Correção: adicionado `roles/iam.serviceAccountAdmin` no módulo wif-bootstrap
  e reaplicado o bootstrap manualmente em dev e prod.
- Aprendizado: ao definir permissões de deploy no bootstrap, sempre listar todos
  os tipos de recursos que o Terraform vai criar (SAs, buckets, Cloud Run, etc.)
  e garantir as roles correspondentes.

**Erro 2 — Corrida entre workflows (race condition)**
- O que aconteceu: `backend-deploy-prod.yml` e `terraform-apply-prod.yml`
  dispararam em paralelo no mesmo push. O deploy rodou antes do Terraform criar
  a infraestrutura, gerando drift — Cloud Run criado fora do state com SA default
  do Compute Engine em vez da `backend-run`.
- Correção: adicionado `needs: [wait-for-terraform]` no `backend-deploy-prod.yml`
  para garantir que o Terraform Apply conclua antes do deploy.
- Aprendizado: em monorepos onde um push pode tocar infra/ e apps/ juntos,
  sempre definir ordem explícita entre workflows de infra e de deploy.

**Erro 3 — Drift em prod após race condition**
- O que aconteceu: o Cloud Run criado com drift precisou ser apagado e recriado
  pelo Terraform. O `terraform apply` em environments/prod foi rodado manualmente
  para reconciliar o state.
- Correção: `gcloud run services delete` seguido de `terraform apply` local com
  credenciais de admin.
- Aprendizado: em ambientes sem tráfego real, apagar e recriar é mais seguro
  que `terraform import`. Com tráfego real, sempre preferir import.

### Mudanças de arquitetura
- Nenhuma mudança em relação ao planejado.

### Status final
- dev: Cloud Run ✅ | Artifact Registry ✅ | GET /health HTTP 200 ✅
- prod: Cloud Run ✅ | Artifact Registry ✅ | GET /health HTTP 200 ✅

---

## Fase 0 — Estrutura e documentação (concluída)

### O que foi feito
- Monorepo criado e pushado para GitHub
- Estrutura de pastas definida (apps/backend, apps/frontend, infra/terraform,
  docs/adr, scripts)
- CLAUDE.md criado com convenções completas do projeto
- .gitignore cobrindo Python/uv, Node/pnpm, Terraform, Docker e segredos
- PRD v1.0 criado com funcionalidades, MVP, métricas de sucesso e roadmap
- ADRs 001-005 criados documentando decisões de arquitetura:
  - ADR-001: Monorepo
  - ADR-002: GCP como cloud provider
  - ADR-003: Terraform com diretórios por ambiente
  - ADR-004: Workload Identity Federation
  - ADR-005: Stack minimalista (FastAPI + React + Cloud Run)

### Erros cometidos e aprendizados
- Nenhum erro técnico nesta fase.
- Aprendizado de processo: definir arquitetura e funcionalidades ANTES de abrir
  o Claude Code evita retrabalho. O CLAUDE.md com contexto completo é o
  investimento mais importante do projeto.

### Mudanças de arquitetura
- Nenhuma.

---

## Próximas fases

| Fase | Descrição | Status |
|---|---|---|
| Fase 1.5 | Dados mock no BigQuery (GA4 público) | ✅ Concluída |
| Fase 2 | MVP: Catálogo + Freshness + Profiling (backend) | ✅ Concluída |
| Fase 2D | Frontend MVP | ✅ Concluída |
| Sprint 2.2 | Metadados de partição, "Ver partições", refresh, busca reversa | ✅ Concluída |
| Sprint 2.3 | 4 melhorias de UX (sidebar, localStorage, not_contains, tabela ordenável) | ✅ Concluída |
| Sprint 3.1 | Auth (Google OAuth), favoritos, histórico, fixes no modal de profiling | ✅ Concluída |
| Sprint 3.2 | Filtros/ordenação, histórico de qualidade, lineage e órfãos, PII, mapa de acesso | ✅ Concluída (7 de 7 itens) |
| Fase 4 | FinOps completo (scanner de desperdício, budget de custo, sugestão de tipo de coluna) | ✅ Concluída (3 de 3 frentes — clustering deferido, ver ADR/spec) |
| — | Admin ACL v1.0–v1.3 (controle de acesso usuário×projeto, projetos públicos, solicitação de acesso, painel "Uso do Hub") | ✅ Concluída |
| — | Documentação para cliente (2 playbooks operacionais + 2 manuais voltados a cliente final) | ✅ Concluída |
| Fase 5 | Storage (Cloud Storage): catálogo, scanner de desperdício (config + uso real), extensão do lineage | ✅ Concluída — validada em dev, mergeada em `main` e deployada em prod (PR #25) |
