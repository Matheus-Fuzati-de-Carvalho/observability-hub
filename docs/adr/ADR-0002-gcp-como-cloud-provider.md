# ADR 0002 — GCP como cloud provider

## Status

Aceito

## Contexto

O Observability Hub monitora datasets e tabelas do BigQuery, que já é a fonte de dados central dos projetos-alvo. A infraestrutura de aplicação precisa hospedar backend e frontend de forma simples, sem exigir orquestração complexa.

## Decisão

Usar exclusivamente o Google Cloud Platform, sem abstrações multi-cloud. BigQuery como fonte de metadados e dados, Cloud Run para hospedar backend e frontend.

## Consequências

- Integração nativa e de baixa latência com BigQuery (`INFORMATION_SCHEMA`, APIs de metadados) e Cloud Logging (audit logs), sem camadas de abstração intermediárias.
- Cloud Run simplifica deploy de containers sem gerenciamento de cluster.
- Autenticação e permissões podem herdar diretamente o modelo IAM do GCP (ex: `bigquery.dataViewer` do usuário autenticado), conforme premissa do PRD.
- Acoplamento a serviços específicos do GCP: portar a ferramenta para outro provedor exigiria reescrever as integrações de metadados e logging.
- Escopo do produto já exclui explicitamente suporte a outros data warehouses além do BigQuery.
