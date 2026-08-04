# ADR 0005 — Stack minimalista (FastAPI + React + Cloud Run)

## Status

Aceito

## Contexto

O produto precisa de um backend que consulte BigQuery e Cloud Logging, e um frontend que exiba os sete domínios de observabilidade (catálogo, lineage, PII, acesso, qualidade, freshness, FinOps). O time é solo nesta fase e o custo/complexidade operacional deve ser mínimo, sem serviços gerenciados adicionais além do necessário.

## Decisão

Backend em Python/FastAPI, frontend em React/Vite/TypeScript com shadcn/ui, ambos empacotados como containers e hospedados em Cloud Run. BigQuery e Cloud Logging são as únicas fontes de dados — sem banco de dados próprio, filas ou serviços intermediários.

## Consequências

- Menos serviços para operar e pagar: sem banco de dados dedicado, sem message broker, sem cache distribuído — o estado vive no BigQuery/Cloud Logging e é consultado sob demanda.
- FastAPI oferece tipagem via Pydantic e boa ergonomia para expor os dados de metadados como API; React/shadcn acelera a construção de UI consistente para os múltiplos domínios do produto.
- Cloud Run hospeda os dois apps de forma simples, com deploy por imagem versionada (tag por git SHA) e sem gerenciamento de cluster.
- Limitação assumida: sem estado persistente próprio da aplicação (ex: configurações de SLA de freshness, preferências de usuário) fica sujeito a decisão futura — hoje o escopo do MVP não exige isso, mas features como "janelas de SLA configuráveis" podem demandar alguma forma de persistência a ser definida em ADR futura.
