"""Client compartilhado do Cloud Storage — mesmo padrão de
core/bigquery.py::get_client() (client cacheado por processo via
lru_cache) e core/logging_client.py::get_logging_client().

`list_bucket_objects_cached` cacheia a listagem de objetos de um bucket
(storage.objects.list) com TTL de 5min, mesmo racional de
core/bigquery.py::get_table_cached — é a chamada cara do domínio
(paginada, custo cresce com o número de objetos), usada por catalog
(tamanho total/contagem) e pelo scanner de desperdício (idade/classe dos
objetos) pra não bater a API a cada refresh de tela.
"""

import threading
import time
from functools import lru_cache

from google.cloud import storage

_BUCKET_OBJECTS_CACHE_TTL_SECONDS = 300
_bucket_objects_cache: dict[str, tuple[float, list[storage.Blob]]] = {}
_bucket_objects_cache_lock = threading.Lock()


@lru_cache
def get_storage_client() -> storage.Client:
    return storage.Client()


def list_bucket_objects_cached(client: storage.Client, bucket_name: str) -> list[storage.Blob]:
    """client.list_blobs(bucket_name) com cache TTL de 5min por bucket."""
    now = time.monotonic()
    with _bucket_objects_cache_lock:
        cached = _bucket_objects_cache.get(bucket_name)
    if cached is not None and now - cached[0] < _BUCKET_OBJECTS_CACHE_TTL_SECONDS:
        return cached[1]
    blobs = list(client.list_blobs(bucket_name))
    with _bucket_objects_cache_lock:
        _bucket_objects_cache[bucket_name] = (now, blobs)
    return blobs
