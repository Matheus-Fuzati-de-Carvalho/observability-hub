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


def _list_objects_or_raise(
    client: storage.Client, project_id: str, bucket_name: str
) -> list[storage.Blob]:
    """list_bucket_objects_cached() com o mesmo tratamento de Forbidden de
    list_buckets() acima — sem isso, um projeto com storage.bucketViewer
    mas sem storage.objectViewer (as duas são necessárias juntas, ver
    docs/specs/storage.md seção 8) estouraria 500 cru aqui em vez do 403
    limpo que o domínio já sabe gerar."""
    try:
        return list_bucket_objects_cached(client, bucket_name)
    except Forbidden as exc:
        raise StorageAccessDeniedError(project_id) from exc


def get_bucket_size_and_count(
    client: storage.Client, project_id: str, bucket_name: str
) -> tuple[int, int]:
    """Soma size_bytes e conta objetos de um bucket (listagem cacheada 5min
    — ver core/storage_client.py). Não há campo agregado nativo no bucket,
    a única forma de saber o tamanho total é listar os objetos."""
    blobs = _list_objects_or_raise(client, project_id, bucket_name)
    total_size = sum(blob.size or 0 for blob in blobs)
    return total_size, len(blobs)


def get_eligible_waste_objects(
    client: storage.Client,
    project_id: str,
    bucket_name: str,
    min_days_unused: int,
    now: datetime,
) -> list[storage.Blob]:
    """Objetos STANDARD do bucket mais antigos que min_days_unused dias
    (customTime como campo primário, updated como fallback — mesmo
    raciocínio já usado no item de freshness, aqui só interno ao scanner).
    Reaproveita a listagem cacheada do catálogo (item 1), sem chamada
    nova. Objeto sem nenhum dos dois timestamps (não deveria acontecer na
    prática — updated é sempre setado pelo GCS) é ignorado, não conta como
    elegível nem quebra o cálculo dos demais."""
    blobs = _list_objects_or_raise(client, project_id, bucket_name)
    eligible = []
    for blob in blobs:
        if blob.storage_class != "STANDARD":
            continue
        reference_time = blob.custom_time or blob.updated
        if reference_time is None:
            continue
        age_days = (now - reference_time).days
        if age_days >= min_days_unused:
            eligible.append(blob)
    return eligible


def get_buckets_sizes_and_counts(
    client: storage.Client, project_id: str, bucket_names: list[str], max_workers: int = 8
) -> dict[str, tuple[int, int]]:
    """Mesma técnica de core/bigquery.py::get_tables_metadata — um bucket
    por thread, cada listagem já usa o cache TTL individual."""
    if not bucket_names:
        return {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(get_bucket_size_and_count, client, project_id, name): name
            for name in bucket_names
        }
        return {futures[future]: future.result() for future in as_completed(futures)}
