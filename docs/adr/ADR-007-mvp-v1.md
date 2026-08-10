# ADR-007 — Funcionalidades do MVP v1

**Status:** Aceito
**Data:** 2026-08-05

---

## Contexto

O PRD lista sete domínios de funcionalidade. Para a primeira versão entregável
do Observability Hub, foi necessário priorizar o que gera valor imediato para
o caso de uso principal: discovery de projetos BigQuery e análise exploratória
de qualidade de dados.

## Decisão

O MVP v1 inclui exclusivamente:

### 1. Seletor de projeto (cross-project)
Campo no frontend para informar o `project_id` alvo. Valida acesso antes de
carregar o catálogo. Contexto global da sessão — todos os módulos operam
sobre o projeto selecionado.

### 2. Catálogo + Volumetria
Inventário navegável de datasets e tabelas via `INFORMATION_SCHEMA`.
Exibe: região, total de tabelas, tamanho em bytes/GB, total de linhas,
tipo de tabela, datas de criação e modificação, particionamento e clustering.
Custo: $0 (metadados gratuitos no BigQuery).

### 3. Freshness com SLA
Monitoramento de atualização de tabelas com janelas configuráveis.
Exibe status visual por tabela (dentro do SLA / alerta / violando).
Fonte: metadados de `last_modified_time` do `INFORMATION_SCHEMA`.

### 4. Profiling coluna a coluna
Análise estatística configurável com:
- Amostragem % (TABLESAMPLE SYSTEM)
- Método de unicidade: HLL/APPROX ou DISTINCT exato
- Filtro temporal por coluna de data + janela em dias
- Dry run com estimativa de custo antes de executar
- SQL auditável exibido na interface
- Métricas por coluna: completude, unicidade, min, max,
  top N valores, tipo lógico inferido, coeficiente de variação
- Métricas por tabela: densidade geral, highlight de colunas
  problemáticas, registros duplicados estimados
- Drill down: distribuição de nulos ao longo do tempo

## Funcionalidades explicitamente fora do MVP v1

- Tabelas vazias / obsoletas — sem valor imediato
- Lineage e tabelas órfãs — Fase 3
- Fingerprinting de PII — Fase 3
- Mapa de acesso — Fase 3
- FinOps (scanner de desperdício, budget) — Fase 4
- Comparação histórica entre execuções de profiling — Fase futura
- Autenticação OAuth por usuário — Fase futura

## Consequências

- Escopo reduzido permite entrega e validação rápida com usuários reais
- Os três módulos do MVP cobrem o caso de uso principal de ponta a ponta:
  discovery (catálogo) → monitoramento (freshness) → qualidade (profiling)
- Todas as funcionalidades fora do MVP estão documentadas no PRD para
  implementação futura
