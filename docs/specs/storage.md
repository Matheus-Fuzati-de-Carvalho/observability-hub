# Spec — `domains/storage` (Cloud Storage)

**Status:** Implementada, validada em dev e em produção — os 4 itens do
MVP (catálogo, colunas nativas de data, scanner de desperdício 6.1+6.2,
extensão do lineage) completos, testados e confirmados em
`observability-hub-dev` pelo usuário em 2026-08-18. Mergeada em `main`
via PR #25 e deployada em `observability-hub-prod` no mesmo dia,
infraestrutura (IAM, buckets mock, dados) promovida antes do merge (ver
`docs/onboarding-cliente.md`)
**Versão:** v1.1
**Depende de:** `domains/lineage` (extensão, não substituição)

---

## 1. Motivação

O Hub hoje só observa BigQuery/Cloud Logging/Cloud Billing. Cloud Storage é
usado intensamente na stack de engenharia de dados do cliente (landing zone,
exports, arquivamento) e aparece nos dois sentidos de pipeline real: como
origem de `LOAD` jobs e como destino de `EXTRACT` jobs do BigQuery. Esta é
a primeira seção de uma frente maior de expansão pra além do BigQuery
(Storage → Scheduler → Workflows, nessa ordem de prioridade — ver Backlog
item 14 do SESSIONLOG). A sidebar já tem `SidebarServiceGroup` pronto pra
comportar um grupo novo sem retrabalho estrutural.

## 2. Escopo do MVP

Quatro funcionalidades, em ordem de dependência (cada uma reaproveita a
anterior):

1. Catálogo de buckets
2. Freshness por bucket
3. Scanner de desperdício (buckets sem lifecycle rule)
4. Extensão do lineage existente pra incluir bucket como nó do grafo

Fora do escopo do MVP (registrar como item futuro, não implementar agora):
- Freshness por prefixo/pasta (mais granular, mais chamadas de API)
- Objetos individuais como nós de lineage (granularidade excessiva —
  decisão já tomada, bucket é o nó, não o objeto)

**Revisado em v1.1**: "objeto nunca lido" no waste scanner **entrou no
escopo** (seção 6.2) depois de Data Access audit logs do GCS terem sido
habilitados em dev (2026-08-18) — não é mais um item futuro, é a checagem
`confidence: "usage_confirmed"`. Continua degradando graciosamente em
projetos sem essa config habilitada (ex: prod hoje).

## 3. Fonte de dados

| Funcionalidade | Fonte | Custo |
|---|---|---|
| Catálogo | `storage.googleapis.com` — listagem de buckets/metadado | Grátis (metadado) |
| Freshness | Metadado de objeto (`updated`, opcionalmente `customTime`) | Grátis (metadado) |
| Waste scanner (6.1) | Metadado de bucket (`lifecycleRule`) + metadado de objeto | Grátis (metadado) |
| Waste scanner (6.2) | Cloud Logging — Data Access audit logs do GCS (`storage.objects.get`), config separada da do BigQuery | Grátis (já habilitado em dev) |
| Lineage (extensão) | Cloud Logging — mesma fonte já usada por `domains/lineage` (audit logs de job do BigQuery) | Grátis (já habilitado) |

Diferente de PII/quality/column-types, nenhuma funcionalidade deste domínio
amostra dado real de objeto — tudo é metadado ou audit log de job do BQ já
existente. Não há necessidade de `TABLESAMPLE`-equivalente nem de cache de
custo por execução.

## 4. Catálogo de buckets

`GET /api/v1/storage/{project}/buckets`

Retorna, por bucket: nome, storage class default, região, tamanho total
(soma de `size` dos objetos — via listagem, não há campo agregado nativo
no bucket), contagem de objetos, `has_lifecycle_rule: bool`, `time_created`
e `updated` (metadado nativo do próprio recurso `Bucket`, incluído de graça
na mesma chamada de listagem — sem custo/chamada extra).

**Decisão**: tamanho total agregado por bucket exige listar objetos
(`storage.objects.list`), que pode ser uma chamada cara em bucket com
muitos objetos. Mesmo padrão de cache TTL já usado em `core/bigquery.py`
(5min) deve se aplicar aqui — `core/storage_client.py` novo, análogo.

## 5. Freshness por bucket

**Revisado em 2026-08-17, depois de validar a v1 em dev** — a v1 desta
seção (endpoint dedicado `GET .../buckets/{bucket}/freshness`, botão "Ver
freshness" sob demanda no frontend, `last_modified` calculado a partir de
`max(customTime ou updated)` entre os **objetos** do bucket) foi
implementada, validada em dev e depois **descartada por decisão do
usuário**, substituída por `time_created`/`updated` do próprio `Bucket`
(seção 4) exibidos como colunas na tabela, sem endpoint/dialog separado.

**Diferença semântica registrada aqui de propósito**: `Bucket.updated` é
quando a **configuração** do bucket mudou (lifecycle, storage class,
IAM...), não quando um objeto foi gravado — bem diferente do
`last_modified` da v1, que refletia atividade de dado real via
`customTime`/`updated` dos objetos. A v1 é uma métrica mais precisa pra
"a esteira de dados desse bucket ainda está viva?"; a v2 é mais barata
(zero chamada extra) mas não responde exatamente a mesma pergunta. Trade-
off aceito conscientemente pelo usuário — código da v1 (`get_bucket_last_
modified` em `repository.py`, endpoint, `BucketFreshnessDialog.tsx`)
removido por completo, não deixado como dead code.

## 6. Scanner de desperdício

`GET /api/v1/storage/{project}/waste-candidates`

Duas checagens independentes, cada uma com sua própria confiabilidade —
não combinadas num único score, mesmo espírito do scanner de desperdício
do FinOps (nunca fabricar um número de aparência precisa sobre suposição
não verificada).

### 6.1 Regra por configuração (idade + ausência de lifecycle rule)

Bucket **sem** `lifecycleRule` configurada E com objetos em `STANDARD`
mais antigos que um limiar configurável (default 60 dias, via
`customTime`/`updated`). Buckets com lifecycle rule configurada nunca
aparecem aqui, mesmo com objetos antigos — a regra observa a **config**,
não só a idade.

Esta checagem é sempre executada, independente de audit log habilitado —
é só metadado. `confidence: "config_based"` na resposta, pra o frontend
diferenciar da checagem 6.2.

**Implementado (2026-08-17)**: `min_days_unused=30|60|90` como `IntEnum`
(mesma correção de `Literal`→422 já feita no FinOps). Reaproveita 100% da
infraestrutura do item 1 (`list_bucket_objects_cached`, `has_lifecycle_
rule`) — nenhuma chamada nova à API do GCS.

### 6.2 Regra por uso real (objeto nunca lido) — depende de Data Access audit logs do GCS

**Habilitado em dev em 2026-08-18** (`DATA_READ` pra
`storage.googleapis.com`, ver `docs/onboarding-cliente.md`). Fonte:
Cloud Logging, mesmo client/roles já usados por lineage/access
(`roles/logging.viewer` + `roles/logging.privateLogViewer`, já
cross-granted — nenhuma role nova necessária pra **ler** o log).

Consulta o audit log de leitura de objeto (`storage.objects.get` e
equivalentes) numa janela de 90 dias (mesma janela já usada por lineage/
access/finops, por consistência). Objeto elegível por 6.1 (idade +
Standard) que **não aparece nenhuma vez** como leitura nessa janela
ganha `confidence: "usage_confirmed"` — sinal mais forte que 6.1 sozinha,
porque combina idade **e** ausência de acesso real.

**Limitação a manter explícita na resposta** (mesmo padrão do `warning`
de lineage): a ausência de evento de leitura na janela não distingue
"nunca lido" de "lido só fora da janela de 90 dias" — sempre comunicar
como "sem leitura registrada nos últimos 90 dias", nunca como "nunca
lido" categórico.

**Ainda não habilitado em prod** — checagem 6.2 deve degradar
graciosamente (retornar só o resultado de 6.1, com aviso explicando por
quê) quando os audit logs do GCS não estiverem habilitados no projeto
consultado. Mesmo padrão de warning condicional já usado por lineage
quando falta `roles/logging.viewer`.

**Nota de volume/custo**: diferente de audit log de job do BigQuery
(evento por job, volume baixo), `DATA_READ` de GCS gera um evento por
operação de leitura de objeto — pode ser volume alto em bucket de
tráfego intenso. Antes de habilitar em prod, medir volume esperado.
Registrar em `docs/onboarding-cliente.md` como item de atenção antes de
replicar a config de dev.

### 6.3 Estimativa de economia

Nunca um valor único — faixa (mesmo padrão do scanner de particionamento
do FinOps), calculada só sobre bytes reais armazenados (`size` ×
diferença de preço STANDARD→NEARLINE/COLDLINE), nunca sobre suposição de
padrão de acesso. Quando 6.2 está disponível e confirma "sem leitura", a
faixa pode ser apresentada com confiança maior (menos disclaimer), mas o
cálculo em si não muda.

**Implementado (2026-08-17)**: a faixa reflete **duas classes de destino
plausíveis** sobre o mesmo byte real armazenado: `NEARLINE` (mínimo,
conservador) e `COLDLINE` (máximo, agressivo). `ARCHIVE` fica de fora de
propósito (custo de retrieval + duração mínima de 365 dias tornam a
recomendação automática arriscada). Preços GCS entram em
`core/config.py` (`gcs_storage_price_usd_per_gb_month_
{standard,nearline,coldline}`), mesmo padrão dos preços do BigQuery já
lá. A limitação de "objeto nunca lido" (6.2) vai sempre preenchida no
campo `limitation` da resposta quando 6.2 não roda, e o campo
`savings_disclaimer` explica a faixa NEARLINE/COLDLINE por completo —
evita que o frontend precise adivinhar o porquê de dois números.

## 7. Extensão do lineage — bucket como nó do grafo

### 7.1 Payloads reais confirmados (2026-08-17/18, `observability-hub-dev`)

Dois formatos capturados ao vivo via `gcloud logging read`, mesma família
`AuditData`/`jobCompletedEvent` (legado) já em uso por `domains/lineage`
pra job de query — **não** é um formato novo, é uma chave irmã dentro do
mesmo `jobConfiguration`.

**LOAD (GCS → BQ)** — `eventName: "load_job_completed"`:
```json
"jobConfiguration": {
  "load": {
    "sourceUris": ["gs://observability-hub-dev-landing/crm_leads/2026-08-17/part-0001.csv"],
    "destinationTable": {
      "projectId": "observability-hub-dev",
      "datasetId": "RAW",
      "tableId": "crm_leads_staging"
    },
    "createDisposition": "CREATE_IF_NEEDED",
    "writeDisposition": "WRITE_APPEND"
  }
}
```

**EXTRACT (BQ → GCS)** — `eventName: "extract_job_completed"`:
```json
"jobConfiguration": {
  "extract": {
    "destinationUris": ["gs://observability-hub-dev-processed/exports/crm_leads_staging.csv"],
    "sourceTable": {
      "projectId": "observability-hub-dev",
      "datasetId": "RAW",
      "tableId": "crm_leads_staging"
    }
  }
}
```

Padrão simétrico: lado BQ sempre vem como `{projectId, datasetId,
tableId}` — mesmo shape já parseado por `domains/lineage` pra job de
query, reaproveitável sem alteração. Lado GCS vem como array de URIs
`gs://bucket/path`; o nó do grafo usa só o bucket (primeiro segmento após
`gs://`), path/arquivo é descartado — consistente com a decisão de bucket
como granularidade do nó, não objeto.

`load`/`extract`/`query` são mutuamente exclusivos dentro de
`jobConfiguration` — o parser despacha por qual chave está presente, sem
ambiguidade.

### 7.2 Mudança no parser (`domains/lineage/repository.py`/`service.py`)

- Novo tipo de nó no grafo: `type: "bucket"` (hoje só existe implicitamente
  `type: "table"`). Frontend (`@xyflow/react`) precisa de um estilo visual
  novo pra diferenciar.
- `load` → aresta `bucket → tabela` (direção: dado flui do bucket pra
  tabela)
- `extract` → aresta `tabela → bucket`
- Mantém a regra já existente de auto-referência nunca virar aresta (não
  deve se aplicar aqui na prática — load/extract sempre têm lados de tipo
  diferente — mas manter a checagem por segurança)

**Revisado durante a implementação (2026-08-18)**: bucket como nó **não**
participa da mesma travessia BFS multi-hop igual a tabela — decisão
tomada com o usuário depois de identificar que, diferente de tabela,
bucket não tem "projeto dono" confiável via API pra saber em qual audit
log procurar quem mais o referencia (o nome do bucket não garante o
projeto GCP que o possui, e jobs que o tocam podem rodar em qualquer
projeto observado pelo Hub, não necessariamente "o projeto do bucket").
**Bucket é sempre nó folha**: entra no grafo (nó + aresta) quando
descoberto a partir dos eventos já buscados pro projeto do lado tabela
(dado que já temos, sem custo extra), mas a travessia nunca tenta
expandir mais a partir dele. `access_denied` nunca é `true` pra um nó
bucket — não existe esse conceito pra ele neste desenho (não fazemos
nenhuma chamada adicional que pudesse falhar por falta de acesso).

**Implementado (2026-08-18)**: `JobEvent` (repository.py) ganhou
`source_buckets`/`destination_buckets`; `_parse_entry` passou a ler
`load.sourceUris` e `extract.{sourceTable,destinationUris}` junto do que
já lia pra `query`/`load.destinationTable`. `NodeRef` em service.py virou
união de `TableRefTuple` (3-tupla) e `BucketRef` (1-tupla,
`(bucket_name,)`) — discriminável só pelo tamanho da tupla, sem precisar
de uma terceira estrutura. `LineageNode` (schemas.py) ganhou `type`
("table"/"bucket") e `bucket_name`; `project_id`/`dataset_id`/`table_id`
viraram opcionais (só preenchidos quando `type="table"`). Frontend:
`LineageGraph.tsx` ganhou `bucketNode` como segundo `nodeTypes` do
`@xyflow/react` (ícone `HardDrive`, cor `status-ok`, mesma identidade
visual do grupo "Cloud Storage" da sidebar).

### 7.3 Não coberto ainda

- Formato do payload quando `sourceUris`/`destinationUris` usa wildcard
  (`gs://bucket/path/*.csv`) — **resolvido por construção**: a extração do
  nome do bucket (primeiro segmento após `gs://`) não depende do resto do
  path ser literal, funciona igual com ou sem glob. Coberto por teste
  unitário (`test_parse_bucket_name_handles_wildcard_path`), ainda não
  visto ao vivo com wildcard real em dev.
- Comportamento quando o job falha (`jobStatus.state != "DONE"`) —
  **continua não coberto, de propósito**: descoberto durante a
  implementação que isso é uma lacuna do domínio `lineage` inteiro (query/
  load/extract), não específica de bucket — nenhum parser de audit log do
  projeto (lineage, access, finops) filtra por status de job hoje. Fora do
  escopo deste item por decisão do usuário; registrar como item de backlog
  do domínio lineage, não do domínio storage.

## 8. IAM necessária

Novo grupo de roles pro checklist de `docs/onboarding-cliente.md`. **Duas**
roles, não uma — descoberto durante a implementação do item 1 (catálogo),
validando em dev: `roles/storage.objectViewer` sozinha não é suficiente,
ver nota abaixo.
- `roles/storage.bucketViewer` (`storage.buckets.get`/`storage.buckets.list`
  — metadado de bucket: nome, storage class, região, lifecycle rule).
  Necessária pro catálogo listar os buckets do projeto antes de olhar
  qualquer objeto dentro deles.
- `roles/storage.objectViewer` (`storage.objects.get`/`storage.objects.list`
  — metadado + leitura de objeto). Necessária pra freshness/waste (tamanho
  agregado, `updated`/`customTime`).
- Nenhuma role nova pra lineage — reaproveita `roles/logging.viewer` +
  `roles/logging.privateLogViewer` já cross-granted pra BigQuery, porque
  o audit log de load/extract já vive dentro do mesmo `bigquery_resource`/
  `data_access` já lido hoje.

> **Nota (2026-08-17, confirmado em dev):** a spec original desta seção
> previa só `roles/storage.objectViewer`. Validando o item 1 em dev, o
> endpoint de catálogo retornou 403 mesmo com essa role concedida —
> `gcloud iam roles describe roles/storage.objectViewer` confirma que ela
> cobre só `storage.objects.*`/`storage.folders.*`/`storage.managedFolders.*`,
> **sem** `storage.buckets.get`/`storage.buckets.list`. `list_buckets()` (a
> primeira chamada do domínio, antes de qualquer coisa por objeto) precisa
> especificamente dessas duas permissões de bucket, que só existem em roles
> como `storage.admin` (controle total, não serve — grava/apaga) ou na role
> dedicada `storage.bucketViewer` (só leitura de metadado de bucket, sem
> acesso a objeto). As duas juntas (`bucketViewer` + `objectViewer`) cobrem
> exatamente as quatro operações de leitura que o domínio usa, sem excesso.

Cross-project: mesma lógica já aplicada a BigQuery/Logging — se o Hub
observa múltiplos projetos, as duas roles precisam ser concedidas
cross-project nos dois sentidos, mesmo padrão de dev↔prod já em uso.

**Nota (v1.1)**: Data Access audit logs (`DATA_READ`) pra
`storage.googleapis.com` habilitados via `auditConfigs` do projeto (não é
uma IAM role — é config de auditoria a nível de projeto, aplicada via
`set-iam-policy`). Confirmado em `observability-hub-dev` em 2026-08-18.
Pendente de habilitação em `observability-hub-prod` — medir volume antes
de replicar (ver seção 6.2).

## 9. Dados mock usados na validação (dev)

Registrado aqui pra rastreabilidade — não é infraestrutura permanente:
- 3 buckets: `observability-hub-dev-landing` (STANDARD, com lifecycle
  rule), `observability-hub-dev-processed` (NEARLINE, sem regra),
  `observability-hub-dev-archive` (COLDLINE, sem regra)
- 1 objeto recente em `landing/crm_leads/{data}/part-0001.csv`
- 1 load job real: `landing/crm_leads/{data}/part-0001.csv` →
  `RAW.crm_leads_staging`
- 1 extract job real: `RAW.crm_leads_staging` →
  `processed/exports/crm_leads_staging.csv`

Não inclui objetos "antigos" simulados via `customTime` — decisão
consciente de adiar validação de freshness/waste com idade real até uma
sessão futura (ver seção 2, fora do escopo por ora quanto a esse teste
específico, mas a regra do scanner já está desenhada pra suportar quando
o mock existir).

## 10. Abertos para decisão antes de implementar

1. Nome do domínio no código: `domains/storage` (mesmo padrão dos
   demais) — confirmar que não colide com algum uso interno da palavra
   "storage" já existente no repo (ex: `core/bigquery.py` não usa esse
   termo hoje, mas vale checar antes de criar o módulo).
2. Onde entra na sidebar: novo grupo `SidebarServiceGroup` próprio
   ("Cloud Storage"), separado de "BigQuery" — confirmar rótulo exato.
3. Threshold default do waste scanner (60 dias sugerido acima) — validar
   com o usuário se faz sentido pro perfil de uso real do cliente.