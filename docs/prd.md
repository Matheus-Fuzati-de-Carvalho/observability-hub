# PRD — Observability Hub

Versão: 1.0
Status: Draft
Última atualização: 2026-08-13 (roadmap)

## 1. Problema

Equipes de consultoria de dados que recebem acesso a projetos GCP já existentes enfrentam três gargalos recorrentes:

1. **Discovery lento** — mapear o que existe (datasets, tabelas, volumes, owners) consome dias de trabalho manual via console GCP ou queries avulsas no BigQuery.
2. **Observabilidade reativa** — SLAs de recebimento de bases são monitorados manualmente ou não são monitorados, e falhas só são percebidas quando alguém nota ausência de dados.
3. **Qualidade de dados cara** — perfilar colunas e tabelas exige escrever queries específicas para cada caso, repetindo esforço a cada novo projeto ou análise.

O Observability Hub resolve esses três gargalos em uma única interface, conectada diretamente ao BigQuery via metadados e audit logs — sem mover dados, sem pipelines adicionais.

## 2. Usuários

| Perfil | Principal dor | Como usa a ferramenta |
|---|---|---|
| Engenheiro de Dados | Discovery de projeto novo, monitorar SLA de ingestão | Catálogo, Freshness, Lineage |
| Cientista de Dados | Entender qualidade e distribuição dos dados antes de modelar | Profiling, PII, Qualidade |
| Analista de BI | Entender volumetria e freshness das fontes que alimentam dashboards | Catálogo, Freshness, FinOps |

## 3. Métricas de sucesso

| Métrica | Sinal de sucesso |
|---|---|
| Tempo de discovery | Engenheiro mapeia projeto novo (datasets, volumetria, freshness) em < 15 minutos |
| Adoção em observabilidade | Uso contínuo e recorrente do painel de Freshness/SLA para bases monitoradas |
| Adoção em qualidade | Profiling usado como passo padrão antes de análises exploratórias e entregas |
| Redução de queries manuais | Usuários param de escrever queries de `INFORMATION_SCHEMA` avulsas |

## 4. Funcionalidades

### 4.1 MVP — sem essas a ferramenta não tem valor

#### Catálogo + Volumetria

Inventário navegável de todos os datasets e tabelas de um projeto GCP, exibindo por padrão:

- Total de tabelas por dataset
- Tamanho em bytes/GB/TB por dataset e por tabela
- Tipo de tabela (nativa, externa, view, materialized view)
- Região do dataset
- Data de criação e última modificação

Por que é MVP: é o ponto de entrada de qualquer processo de discovery. Sem isso, o usuário não sabe nem o que existe.

#### Freshness com SLA

Monitoramento de atualização de tabelas com configuração de janelas de SLA:

- Janelas configuráveis: 12h, 24h, 48h, ou personalizada
- Status visual por tabela: dentro do SLA (verde), em alerta (amarelo), violando (vermelho), obsoleta
- Histórico de atualizações dos últimos 30 dias
- Detecção de tabelas que pararam de atualizar silenciosamente

Por que é MVP: o segundo caso de uso mais crítico — observabilidade de recebimento de bases é uso contínuo e diário.

#### Profiling de qualidade — coluna a coluna, tabela a tabela

Análise estatística configurável de qualquer tabela, com os seguintes controles:

**Filtros de escopo (aplicados antes do scan):**

- `TABLESAMPLE SYSTEM (x PERCENT)` — amostragem configurável para tabelas grandes
- Filtro temporal: selecionar qualquer coluna de data/timestamp da tabela e definir janela (ex: últimos 7, 30, 90 dias ou range customizado)

**Métricas por coluna:**

- Contagem total de linhas
- Null count e Null share (%)
- Distinct count via `HLL_COUNT.INIT` / `HLL_COUNT.MERGE` (BigQuery nativo, custo quase zero)
- Valor mínimo e máximo (para tipos numéricos e de data)
- Top 5 valores mais frequentes (para colunas de baixa cardinalidade)

**Dry Run antes de executar:**

- Calcula bytes escaneados estimados e custo em USD antes de rodar o profiling real
- Usuário decide se prossegue ou ajusta filtros

Por que é MVP: elimina o maior gargalo de qualidade — escrever queries de profiling do zero para cada tabela e coluna.

### 4.2 Fase 2 — alto valor, após MVP estabilizado

**Lineage e tabelas órfãs**

- Reconstrução de dependências entre tabelas via Cloud Logging (audit logs de jobs BigQuery)
- Identificação de tabelas sem consumidores conhecidos (órfãs)
- Mapeamento de quais jobs/queries alimentam cada tabela

**Fingerprinting de PII**

- Detecção automática de colunas com dados pessoais (CPF, email, telefone, nome) via amostragem
- Classificação de sensibilidade por tabela (pública, interna, restrita)

**Mapa de acesso**

- Quem acessou quais tabelas e quando (Cloud Logging)
- Distinção entre acessos humanos e service accounts
- Últimos N usuários que consultaram cada tabela

### 4.3 Fase 3 — FinOps e governança

**Scanner de desperdício**

- Tabelas sem acesso nos últimos 30/60/90 dias
- Tabelas sem particionamento que seriam beneficiadas
- Estimativa de economia potencial

**Budget por dataset/projeto**

- Custo mensal por dataset
- Top 10 queries mais caras
- Top usuários/service accounts por gasto
- Projeção de custo do mês

**Otimizações sugeridas**

- Recomendações automáticas de particionamento, clustering e tipo de coluna com estimativa de economia

### 4.4 Fase 5 — Cloud Storage (primeira expansão pra além do BigQuery)

Ver `docs/specs/storage.md` pra detalhe completo. Quatro funcionalidades,
mesma filosofia de custo mínimo do resto do produto (metadado/audit log,
nunca amostragem de dado real de objeto):

- **Catálogo de buckets**: nome, storage class, região, tamanho total,
  contagem de objetos, lifecycle rule, data de criação/atualização.
- **Scanner de desperdício**: duas checagens — idade + ausência de
  lifecycle rule (sempre disponível) e confirmação de "sem leitura
  recente" via Data Access audit log do GCS (opcional, precisa de config
  de audit separada da do BigQuery). Faixa de economia estimada
  (migração pra NEARLINE/COLDLINE), nunca um valor único.
- **Extensão do lineage**: bucket vira nó do grafo já existente (jobs
  LOAD/EXTRACT do BigQuery) — sempre nó folha, não expande recursivamente
  a partir de um bucket (sem forma confiável de saber "o projeto dono" de
  um bucket via API).

## 5. Fora do escopo (explicitamente)

- Mover, transformar ou gravar dados — a ferramenta é somente leitura
- Suporte a outros data warehouses além do BigQuery
- Alertas via email/Slack (pode entrar em fase futura, não é MVP)
- Controle de acesso granular dentro da ferramenta (herda permissões do GCP do usuário autenticado)

## 6. Restrições e premissas

- A ferramenta roda no GCP (Cloud Run) e acessa BigQuery via `INFORMATION_SCHEMA` e APIs de metadados — sem queries em dados reais, exceto no profiling onde o usuário explicitamente solicita
- Custo de operação deve ser mínimo — preferir metadados e HLL a full table scans
- O usuário autenticado precisa ter no mínimo permissão de `bigquery.dataViewer` no projeto alvo
- Ambientes separados: dev (`observability-hub-dev`) e prod (`observability-hub-prod`)

## 7. Roadmap de fases

| Fase | Entregas | Status |
|---|---|---|
| Fase 0 | Estrutura do monorepo, CLAUDE.md, convenções | ✅ Concluída |
| Fase 1 | Bootstrap Terraform, CI/CD, Cloud Run vazio deployado | ✅ Concluída |
| Fase 2 | MVP: Catálogo + Volumetria + Freshness + Profiling (backend + frontend) | ✅ Concluída |
| Sprint 2.2/2.3 | Metadados de partição, busca reversa tabela→datasets, refresh e melhorias de UX sobre o MVP do Catálogo | ✅ Concluída |
| Fase 3 | Lineage, PII, Mapa de acesso | ✅ Concluída |
| Fase 4 | FinOps completo | ✅ Concluída (scanner de desperdício, budget e sugestão de tipo de coluna; sugestão de clustering deferida — ver docs/specs/finops-column-types.md, "Fora do escopo") |
| Fase 5 | Storage (Cloud Storage): catálogo, scanner de desperdício, extensão do lineage | ✅ Concluída — validada em dev, mergeada em `main` e deployada em prod (PR #25) |

Ver `CHANGELOG.md` para o detalhe fase a fase (o que foi feito, erros
corrigidos e decisões de arquitetura) e `SESSIONLOG.md` para o estado
mais recente da sessão de desenvolvimento.
