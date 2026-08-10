"""Client compartilhado do BigQuery e descoberta automática de regiões.

A lib google-cloud-bigquery é síncrona; por isso get_client() e
discover_regions() são funções `def` (não `async def`) e a paralelização
entre regiões usa threads, não asyncio — ver CLAUDE.md, convenção de
backend, e o desvio documentado na spec docs/specs/catalog.md.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import bigquery

from observability_hub.core.config import BQ_REGIONS, settings
from observability_hub.core.exceptions import (
    DatasetNotFoundError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
)


@lru_cache
def get_client() -> bigquery.Client:
    return bigquery.Client()


def _probe_region(client: bigquery.Client, project_id: str, region: str) -> str | None:
    """Retorna a região se o projeto tiver ao menos um dataset nela, ou None
    se a região existir mas não tiver datasets. Propaga Forbidden/NotFound
    para o chamador classificar."""
    query = (
        f"SELECT schema_name FROM `{project_id}.region-{region}"
        ".INFORMATION_SCHEMA.SCHEMATA` LIMIT 1"
    )
    rows = list(client.query(query).result())
    return region if rows else None


def discover_regions(
    project_id: str,
    client: bigquery.Client | None = None,
    regions: list[str] | None = None,
    probe: Callable[[bigquery.Client, str, str], str | None] = _probe_region,
) -> list[str]:
    """
    Consulta INFORMATION_SCHEMA.SCHEMATA em todas as regiões conhecidas em
    paralelo (threads) e retorna as regiões onde o projeto tem ao menos um
    dataset. Lista vazia é um resultado válido (projeto acessível sem
    datasets), não um erro.

    Levanta ProjectNotFoundError se todas as regiões responderem NotFound
    (projeto inexistente). Levanta ProjectAccessDeniedError se qualquer
    região responder Forbidden.
    """
    client = client if client is not None else get_client()
    regions = regions if regions is not None else BQ_REGIONS

    found_regions: list[str] = []
    forbidden_count = 0
    notfound_count = 0

    with ThreadPoolExecutor(max_workers=settings.region_discovery_max_workers) as pool:
        futures = {pool.submit(probe, client, project_id, region): region for region in regions}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Forbidden:
                forbidden_count += 1
            except NotFound:
                notfound_count += 1
            else:
                if result is not None:
                    found_regions.append(result)

    if found_regions:
        return sorted(found_regions)
    if notfound_count == len(regions):
        raise ProjectNotFoundError(project_id)
    if forbidden_count > 0:
        raise ProjectAccessDeniedError(project_id)
    return []


def resolve_dataset_region(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    candidate_regions: list[str],
) -> str:
    """Descobre em qual região está um dataset_id. Vários domínios (catalog,
    freshness, ...) recebem apenas dataset_id nos endpoints, sem region —
    dataset_id é único por projeto independente da região, então basta
    encontrar a primeira região candidata que bate."""
    for region in candidate_regions:
        query = f"""
            SELECT location
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.SCHEMATA`
            WHERE schema_name = @dataset_id
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id)]
        )
        rows = list(client.query(query, job_config=job_config).result())
        if rows:
            return region
    raise DatasetNotFoundError(project_id, dataset_id)
