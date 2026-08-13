import pytest

from observability_hub.core import bigquery as bigquery_module
from observability_hub.core import secrets as secrets_module


@pytest.fixture(autouse=True)
def _clear_bigquery_table_cache():
    """core.bigquery.get_table_cached/get_tables_metadata cacheiam por
    table_ref (string), não por instância de client — em produção há um
    único client, mas em testes cada teste cria seu próprio MagicMock.
    Sem limpar entre testes, dois testes usando o mesmo table_ref (comum:
    "proj.RAW.ga4_events") vazam o resultado cacheado de um client mockado
    para o outro."""
    bigquery_module._table_cache.clear()
    yield
    bigquery_module._table_cache.clear()


@pytest.fixture(autouse=True)
def _clear_secrets_cache():
    """core.secrets.get_secret/_is_prod são @lru_cache — sem limpar entre
    testes, o valor (ou o mock) da primeira chamada vaza pros testes
    seguintes, mesmo trocando o monkeypatch."""
    secrets_module.get_secret.cache_clear()
    secrets_module._is_prod.cache_clear()
    yield
    secrets_module.get_secret.cache_clear()
    secrets_module._is_prod.cache_clear()
