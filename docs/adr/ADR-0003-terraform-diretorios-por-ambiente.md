# ADR 0003 — Terraform com diretórios por ambiente (não workspaces)

## Status

Aceito

## Contexto

O projeto mantém dois ambientes GCP totalmente separados (`observability-hub-dev` e `observability-hub-prod`), cada um com seu próprio state, service accounts, secrets e imagens. Terraform workspaces permitem múltiplos states a partir de uma única raiz de código, mas compartilham a mesma configuração e aumentam o risco de aplicar mudanças no ambiente errado por engano (ex: workspace selecionado incorretamente no CI).

## Decisão

Cada ambiente é uma raiz de execução Terraform independente: `infra/terraform/environments/dev` e `infra/terraform/environments/prod`, ambas consumindo os mesmos módulos reutilizáveis em `infra/terraform/modules/`. Não usar Terraform workspaces.

## Consequências

- Isolamento total entre ambientes: é estruturalmente impossível aplicar mudanças em prod estando na pasta de dev, pois cada diretório tem seu próprio backend de state e variáveis.
- O ambiente-alvo é determinado pelo diretório de execução, não por uma flag de runtime ou workspace selecionado — reduz erro humano e simplifica a lógica dos workflows de CI/CD.
- Alinhado à recomendação da HashiCorp de evitar workspaces para ambientes com requisitos de isolamento crítico.
- Custo: alguma duplicação de declaração entre `environments/dev` e `environments/prod` (mitigada por módulos compartilhados em `modules/`).
