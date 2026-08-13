# ADR-008 — Sem job "Plan (prod)" em terraform-plan.yml

**Status:** Aceito
**Data:** 2026-08-13

---

## Contexto

`terraform-plan.yml` roda em todo `pull_request` que toca
`infra/terraform/environments/**` ou `infra/terraform/modules/**`, com o
objetivo de mostrar o `terraform plan` antes do merge — feedback de review
sobre o que vai mudar na infraestrutura.

O Workload Identity Federation de prod (`infra/terraform/bootstrap/prod`,
ver ADR-004) tem `attribute_condition` restrito a
`assertion.ref == "refs/heads/main"` — só autentica em push direto para
`main`, nunca em `pull_request` (que roda contra `refs/pull/N/merge`, não
`refs/heads/main`). Essa restrição é intencional: garante que a identidade
de deploy de prod só é alcançável depois que o código já está em `main`,
nunca a partir de uma branch ou PR ainda em revisão.

Um job "Plan (prod)" em `terraform-plan.yml`, disparado por
`pull_request`, falharia na etapa de autenticação em toda execução — o WIF
de prod nunca aceitaria a assertion vinda de um evento de PR. Não é um bug
a ser corrigido; é a mesma restrição que protege o `apply` de prod
funcionando exatamente como desenhado, só que aplicada também ao `plan`.

## Decisão

`terraform-plan.yml` só tem um job, `Plan (dev)`. Não existe (e não haverá,
sem revisitar essa decisão) um job `Plan (prod)` nesse workflow.

Revisão de `terraform plan` para mudanças em prod é **manual**:
quem revisa um PR que toca `infra/terraform/**` roda
`terraform plan` localmente contra `infra/terraform/environments/prod`
antes de aprovar/mergear, usando suas próprias credenciais (não a
service account de CI). Essa responsabilidade já está documentada em
CLAUDE.md, seção CI/CD.

O `apply` de prod continua totalmente automatizado
(`terraform-apply-prod.yml`, disparado por push/merge em `main`) — só a
etapa de `plan` pré-merge é manual, não o `apply` pós-merge.

## Alternativas consideradas

**Afrouxar o `attribute_condition` do WIF de prod para aceitar também
eventos de `pull_request`.** Rejeitada: enfraquece a garantia de segurança
que o WIF de prod existe para dar — a identidade de deploy de prod passaria
a ser alcançável a partir de qualquer PR aberto, antes de qualquer review
ou merge. O ganho (plan de prod visível no PR) não compensa o risco.

**Pool/provider de WIF separado, só-leitura, escopado pra permitir plan
(não apply) a partir de eventos de PR.** Mais seguro que afrouxar o WIF
existente, mas adiciona um segundo pool WIF, um segundo conjunto de
secrets do GitHub e mais superfície de manutenção — desproporcional ao
estágio atual do projeto (MVP, time pequeno). Fica registrado como opção
futura, não descartada definitivamente.

**Rodar terraform plan de prod em runner self-hosted dentro da rede/projeto
prod**, evitando WIF via GitHub-hosted runner. Rejeitada por complexidade
operacional (manter um runner) desproporcional ao problema.

## Consequências

- Quem revisa um PR que toca `infra/terraform/**` precisa lembrar de rodar
  `terraform plan` manual contra prod antes de aprovar — não há mais
  nenhum sinal automatizado de CI para isso. Risco de esquecimento existe
  e é aceito conscientemente.
- A identidade de deploy de prod (WIF) nunca é alcançável a partir de um
  evento de `pull_request`, só de push já mergeado em `main` — superfície
  de ataque menor.
- `terraform-plan.yml` fica mais simples (um job só) em vez de ter um job
  "Plan (prod)" que falharia sistematicamente por design.
- Se algum dia a automação do plan de prod em PR virar necessidade real
  (ex: time cresce, revisão manual vira gargalo), a opção do pool WIF
  separado (só-leitura) descrita acima é o próximo passo a avaliar — não
  afrouxar o WIF de prod existente.
