"""Consulta buckets/objetos do Cloud Storage via client REST
(google-cloud-storage). Mesma classe de erro que domains/lineage já
aprendeu da forma difícil (core/logging_client.py): o client de Storage
também é REST, não gRPC — um 403 aqui levanta
google.api_core.exceptions.Forbidden, não PermissionDenied.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from google.api_core.exceptions import Forbidden
from google.cloud import storage

from observability_hub.core.exceptions import StorageAccessDeniedError
from observability_hub.core.storage_client import list_bucket_objects_cached


def list_buckets(client: storage.Client, project_id: str) -> list[storage.Bucket]:
    """Lista os buckets do projeto. Levanta StorageAccessDeniedError se a SA
    não tiver roles/storage.bucketViewer (storage.objectViewer sozinha não
    cobre storage.buckets.list — ver docs/specs/storage.md seção 8)."""
    try:
        return list(client.list_buckets(project=project_id))
    except Forbidden as exc:
        raise StorageAccessDeniedError(project_id) from exc


def get_bucket_size_and_count(client: storage.Client, bucket_name: str) -> tuple[int, int]:
    """Soma size_bytes e conta objetos de um bucket (listagem cacheada 5min
    — ver core/storage_client.py). Não há campo agregado nativo no bucket,
    a única forma de saber o tamanho total é listar os objetos."""
    blobs = list_bucket_objects_cached(client, bucket_name)
    total_size = sum(blob.size or 0 for blob in blobs)
    return total_size, len(blobs)


def get_bucket_last_modified(client: storage.Client, bucket_name: str) -> datetime | None:
    """max(customTime ou updated) entre os objetos do bucket — customTime é
    primário quando presente (setável pelo pipeline do cliente pra refletir
    a data lógica do dado, ex: partição), updated (timestamp de upload
    real) é o fallback. None se o bucket não tem objetos (não é erro —
    quem chama decide como sinalizar essa ambiguidade)."""
    blobs = list_bucket_objects_cached(client, bucket_name)
    timestamps = [blob.custom_time or blob.updated for blob in blobs]
    timestamps = [t for t in timestamps if t is not None]
    return max(timestamps) if timestamps else None


def get_buckets_sizes_and_counts(
    client: storage.Client, bucket_names: list[str], max_workers: int = 8
) -> dict[str, tuple[int, int]]:
    """Mesma técnica de core/bigquery.py::get_tables_metadata — um bucket
    por thread, cada listagem já usa o cache TTL individual."""
    if not bucket_names:
        return {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(get_bucket_size_and_count, client, name): name for name in bucket_names
        }
        return {futures[future]: future.result() for future in as_completed(futures)}
