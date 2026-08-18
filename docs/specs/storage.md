# Spec — `domains/storage` (Cloud Storage)

**Status:** Proposta — não implementada
**Versão:** v1.0
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
- "Objeto nunca lido" no waste scanner — depende de Data Access audit logs
  do GCS habilitados, que é uma config de audit **separada** da do
  BigQuery (não vem de graça pela IAM já concedida pra BQ/Logging hoje).
  Ver seção 6.

## 3. Fonte de dados

| Funcionalidade | Fonte | Custo |
|---|---|---|
| Catálogo | `storage.googleapis.com` — listagem de buckets/metadado | Grátis (metadado) |
| Freshness | Metadado de objeto (`updated`, opcionalmente `customTime`) | Grátis (metadado) |
| Waste scanner | Metadado de bucket (`lifecycleRule`) + metadado de objeto | Grátis (metadado) |
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

Regra do MVP: bucket **sem** `lifecycleRule` configurada E com objetos em
`STANDARD` mais antigos que um limiar configurável (default 60 dias, via
`customTime`/`updated`). Buckets com lifecycle rule configurada nunca
aparecem, mesmo com objetos antigos — a regra observa a **config**, não
só a idade (mesmo espírito do scanner de tabelas sem uso do FinOps: nunca
fabricar economia sobre suposição não verificada).

**Limitação explícita, documentada na resposta** (não implementada no
MVP): não há verificação de "objeto nunca lido" — isso exigiria Data
Access audit logs do GCS, habilitados separadamente dos do BigQuery. Sem
essa config, a API deve dizer isso explicitamente em vez de simular uma
certeza que não tem, mesmo padrão do `warning` de lineage. Adicionar como
novo item ao checklist de `docs/onboarding-cliente.md` quando essa
funcionalidade for implementada (não faz parte deste MVP).

Estimativa de economia: nunca um valor único — faixa (mesmo padrão do
scanner de particionamento do FinOps), calculada só sobre bytes reais
armazenados (`size` × diferença de preço STANDARD→NEARLINE), nunca sobre
suposição de padrão de acesso.

**Implementado (2026-08-17)**: `GET /api/v1/storage/{project}/waste-
candidates?min_days_unused=30|60|90` (`IntEnum`, mesma correção de
`Literal`→422 já feita no FinOps). Diferente do FinOps (que ancora a
faixa em custo de scan *observado*), aqui não há sinal de acesso real
disponível — a faixa reflete **duas classes de destino plausíveis** sobre
o mesmo byte real armazenado: `NEARLINE` (mínimo, conservador) e
`COLDLINE` (máximo, agressivo). `ARCHIVE` fica de fora de propósito
(custo de retrieval + duração mínima de 365 dias tornam a recomendação
automática arriscada). Preços GCS entram em `core/config.py`
(`gcs_storage_price_usd_per_gb_month_{standard,nearline,coldline}`),
mesmo padrão dos preços do BigQuery já lá. Reaproveita 100% da
infraestrutura do item 1 (`list_bucket_objects_cached`, `has_lifecycle_
rule`) — nenhuma chamada nova à API do GCS. A limitação de "objeto nunca
lido" vai sempre preenchida no campo `limitation` da resposta (não
condicional), e o campo `savings_disclaimer` explica a faixa NEARLINE/
COLDLINE por completo — evita que o frontend precise adivinhar o porquê
de dois números.

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
- Bucket como nó participa da mesma travessia BFS multi-hop já existente
  (`max_hops`) — não é uma estrutura de grafo paralela. Se um bucket for
  alcançado e pertencer a um projeto sem acesso, aplica a mesma regra já
  existente pra tabela não-raiz (`access_denied=true`, ramo não expande,
  resto do grafo segue).

### 7.3 Não coberto ainda

- Formato do payload quando `sourceUris`/`destinationUris` usa wildcard
  (`gs://bucket/path/*.csv`) — extração do nome do bucket continua válida
  (primeiro segmento), mas não testado ao vivo com wildcard real.
- Comportamento quando o job falha (`jobStatus.state != "DONE"`) — mesmo
  tratamento que lineage já dá pra job de query com erro, a confirmar que
  se aplica igual aqui.

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