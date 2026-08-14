# ADR-006 — Modelo de acesso cross-project (Modelo A)

**Status:** Aceito
**Data:** 2026-08-05

---

## Contexto

O Observability Hub precisa consultar metadados de projetos GCP arbitrários —
não apenas o projeto onde o Hub está hospedado. O caso de uso principal é
consultoria: o usuário chega em um projeto de cliente e quer inspecionar seus
datasets e tabelas sem precisar instalar nada no projeto alvo.

## Decisão

Adotar o **Modelo A — Service Account com acesso cross-project.**

A service account de runtime do Cloud Run (`backend-run`) recebe a role
`roles/bigquery.metadataViewer` nos projetos alvo. O projeto alvo é informado
pelo usuário via campo no frontend e passado como parâmetro em todos os
endpoints da API.

O frontend armazena o `project_id` selecionado como contexto global da sessão
— todos os módulos (catálogo, freshness, profiling) operam sobre esse projeto.

## Como conceder acesso a um projeto alvo

O administrador do projeto alvo executa uma vez. A lista de roles cresceu
desde a decisão original deste ADR (que previa só `metadataViewer`) — o
checklist completo e atualizado, incluindo `jobUser`/`dataViewer`
(profiling) e `logging.viewer` + Data Access audit logs (lineage), vive em
[`docs/onboarding-cliente.md`](../onboarding-cliente.md), mantido como
documento operacional vivo em vez de duplicado aqui.

## Alternativas consideradas

**Modelo B — OAuth por usuário:** o Hub usa o token do usuário autenticado
para queries no BQ. Mais seguro e flexível (herda permissões do usuário),
mas requer implementação de OAuth + token forwarding. Complexidade
desproporcional para o MVP.

## Consequências

- Simples de implementar — sem OAuth, sem troca de tokens
- Funciona bem para consultoria onde o usuário tem acesso admin ao projeto alvo
- Requer um comando manual por projeto alvo para liberar acesso à SA
- Se a SA não tiver acesso ao projeto informado, a API retorna HTTP 403 com
  mensagem orientando o comando de concessão
