"""Client compartilhado do Firestore — mesmo padrão de
core/bigquery.py::get_client() (client cacheado por processo via
lru_cache, sem estado por request). Usado pelos domínios favorites e
history.
"""

from functools import lru_cache

from google.cloud import firestore


@lru_cache
def get_firestore_client() -> firestore.Client:
    return firestore.Client()
