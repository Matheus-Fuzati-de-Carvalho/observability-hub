# ADR 0004 — Workload Identity Federation (sem service account keys)

## Status

Aceito

## Contexto

Os workflows de CI/CD no GitHub Actions precisam autenticar no GCP para buildar imagens, aplicar Terraform e fazer deploy no Cloud Run. O método tradicional de usar chaves de service account (JSON) armazenadas como secret do GitHub introduz risco de vazamento, já que são credenciais de longa duração e sem expiração automática.

## Decisão

Autenticar GitHub Actions no GCP exclusivamente via Workload Identity Federation (WIF): o pool e provider WIF são criados uma vez em `infra/terraform/bootstrap`, e os workflows trocam o token OIDC do GitHub por credenciais de curta duração do GCP, sem nenhuma chave de service account em segredo do GitHub.

## Consequências

- Elimina o risco de vazamento de chaves de longa duração — não há credencial estática para rotacionar ou vazar.
- Segue a prática de segurança recomendada pelo GCP para autenticação de CI/CD externo.
- Configuração inicial mais complexa que uma chave de service account (exige pool, provider, binding de IAM por repositório/branch), mas é feita uma única vez em `bootstrap` por ambiente.
- `infra/terraform/bootstrap` precisa ser aplicado manualmente (fora do CI), já que os workflows dependem do WIF que ele mesmo cria — dependência circular resolvida por essa exceção documentada em CLAUDE.md.
