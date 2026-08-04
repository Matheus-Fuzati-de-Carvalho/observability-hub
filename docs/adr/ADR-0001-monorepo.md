# ADR 0001 — Monorepo

## Status

Aceito

## Contexto

O projeto tem backend (FastAPI), frontend (React) e infraestrutura (Terraform) que evoluem juntos e são mantidos, no momento, por um time solo. Ferramentas como Claude Code funcionam melhor com contexto completo do projeto disponível em um único lugar, e a operação (CI/CD, versionamento, revisão) precisa ser simples nesta fase do projeto.

## Decisão

Usar um monorepo: app (backend + frontend), infraestrutura (Terraform) e documentação versionados juntos no mesmo repositório Git.

## Consequências

- Contexto completo do projeto (código, infra, docs) fica acessível em um único checkout, favorecendo sessões de Claude Code e revisão humana.
- Simplicidade operacional: um único repositório para clonar, um único histórico de commits, sem sincronização entre repositórios separados.
- CI/CD precisa distinguir o que mudou (backend, frontend, infra) para acionar apenas os workflows relevantes, já refletido na convenção de múltiplos workflows por app/ambiente em `.github/workflows/`.
- Caso o time cresça significativamente ou os componentes precisem de ciclos de release independentes, a decisão deve ser revisitada.
