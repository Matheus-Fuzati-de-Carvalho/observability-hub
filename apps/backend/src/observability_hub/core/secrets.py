"""Leitura de secrets do Secret Manager em runtime — nunca via variável de
ambiente estática (CLAUDE.md, Guardrails). Usado hoje só pelo domínio auth
(credenciais OAuth, JWT_SECRET, allowlist), mas mora em core/ porque não é
específico de um domínio.
"""

import json
from functools import lru_cache

from google.cloud import secretmanager

from observability_hub.core.bigquery import get_runtime_project

# GOOGLE_OAUTH_CLIENT_ID/SECRET têm um secret por ambiente (_DEV/_PROD) —
# são OAuth clients distintos no Google Cloud Console, um por conjunto de
# URLs de callback registradas. JWT_SECRET e OAUTH_ALLOWLIST usam o mesmo
# nome (e valor) nos dois projetos.
_DEV_SUFFIX = "-dev"
_PROD_SUFFIX = "-prod"


@lru_cache
def _is_prod() -> bool:
    return get_runtime_project().endswith(_PROD_SUFFIX)


@lru_cache
def get_secret(secret_id: str) -> str:
    """access_secret_version na versão "latest" — cacheado por processo
    (mesmo racional do get_table_cached de core/bigquery.py: secrets não
    mudam com frequência, e cada leitura é uma chamada de API)."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{get_runtime_project()}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode("utf-8")


def get_oauth_client_id() -> str:
    return get_secret("GOOGLE_OAUTH_CLIENT_ID_PROD" if _is_prod() else "GOOGLE_OAUTH_CLIENT_ID_DEV")


def get_oauth_client_secret() -> str:
    secret_id = (
        "GOOGLE_OAUTH_CLIENT_SECRET_PROD" if _is_prod() else "GOOGLE_OAUTH_CLIENT_SECRET_DEV"
    )
    return get_secret(secret_id)


def get_jwt_secret() -> str:
    return get_secret("JWT_SECRET")


def get_oauth_allowlist() -> dict:
    """{"allowed_domains": [...], "allowed_emails": [...]}"""
    return json.loads(get_secret("OAUTH_ALLOWLIST"))
