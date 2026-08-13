"""Client compartilhado do Cloud Logging — mesmo padrão de
core/bigquery.py::get_client() (client cacheado por processo via
lru_cache). Usado por domains/lineage (audit logs de BigQuery) e, no
futuro, por domains/access (mapa de acesso), que lê a mesma fonte de
audit logs.
"""

from functools import lru_cache

from google.cloud import logging as cloud_logging


@lru_cache
def get_logging_client() -> cloud_logging.Client:
    return cloud_logging.Client()
