"""Só fala com o Cloud Logging — extrai eventos de job completado do
BigQuery a partir de audit logs (Data Access, categoria opcional —
precisa estar habilitada no projeto alvo; ver domains/lineage/service.py
sobre o aviso devolvido quando o resultado vem vazio).

Formato do payload documentado em
https://docs.cloud.google.com/bigquery/docs/reference/auditlogs/migration
(BigQueryAuditMetadata, "jobChange"). Ainda não validado contra logs
reais deste projeto — Data Access audit logs estavam desabilitados em
dev/prod no momento em que este domínio foi implementado.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from google.api_core.exceptions import PermissionDenied
from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from observability_hub.core.exceptions import LoggingAccessDeniedError

LOOKBACK_DAYS = 30
_PAGE_SIZE = 1000

TableRefTuple = tuple[str, str, str]  # (project_id, dataset_id, table_id)


@dataclass(frozen=True)
class JobEvent:
    job_id: str
    principal_email: str
    referenced_tables: list[TableRefTuple]
    destination_table: TableRefTuple | None


def _parse_table_ref(ref: str | None) -> TableRefTuple | None:
    """ "projects/{p}/datasets/{d}/tables/{t}" -> (p, d, t); None se o
    formato não bater (defensivo — não deve travar o parsing de um job
    inteiro por causa de uma referência inesperada)."""
    if not ref:
        return None
    parts = ref.split("/")
    if len(parts) != 6 or parts[0] != "projects" or parts[2] != "datasets" or parts[4] != "tables":
        return None
    return parts[1], parts[3], parts[5]


def _parse_entry(entry: cloud_logging.LogEntry) -> JobEvent | None:
    payload = entry.payload if isinstance(entry.payload, dict) else None
    if payload is None:
        return None

    job = payload.get("metadata", {}).get("jobChange", {}).get("job", {})
    if not job:
        return None

    job_stats = job.get("jobStats", {}).get("queryStats", {})
    raw_referenced = job_stats.get("referencedTables", [])
    referenced = [ref for r in raw_referenced if (ref := _parse_table_ref(r)) is not None]

    job_config = job.get("jobConfig", {})
    destination_raw = job_config.get("queryConfig", {}).get("destinationTable") or job_config.get(
        "loadConfig", {}
    ).get("destinationTable")
    destination = _parse_table_ref(destination_raw)

    job_name_parts = job.get("jobName", "").split("/")
    job_id = job_name_parts[3] if len(job_name_parts) > 3 else job.get("jobName", "")
    principal_email = payload.get("authenticationInfo", {}).get("principalEmail", "")

    return JobEvent(
        job_id=job_id,
        principal_email=principal_email,
        referenced_tables=referenced,
        destination_table=destination,
    )


def list_job_events(client: cloud_logging.Client, project_id: str) -> list[JobEvent]:
    """Levanta LoggingAccessDeniedError se a SA de runtime não tiver
    roles/logging.viewer no projeto. Lista vazia (sem erro) é o resultado
    tanto de "nenhum job rodou na janela" quanto de "Data Access audit
    logs desabilitados" — os dois casos são indistinguíveis por aqui, ver
    aviso estático em domains/lineage/service.py."""
    cutoff = (datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    filter_ = (
        'resource.type="bigquery_resource" '
        'protoPayload.methodName="jobservice.jobcompleted" '
        f'timestamp>="{cutoff}"'
    )
    try:
        entries = client.list_entries(
            resource_names=[f"projects/{project_id}"],
            filter_=filter_,
            page_size=_PAGE_SIZE,
        )
        return [event for entry in entries if (event := _parse_entry(entry)) is not None]
    except PermissionDenied as exc:
        raise LoggingAccessDeniedError(project_id) from exc


def list_all_table_refs(
    client: bigquery.Client, project_id: str, regions: list[str], max_workers: int = 8
) -> list[tuple[str, str]]:
    """Todas as (dataset_id, table_id) do projeto, via INFORMATION_SCHEMA
    por região em paralelo — mesma técnica de
    domains/catalog/repository.py::search_tables. Duplicado em vez de
    importado de catalog porque nenhum domínio deste projeto importa de
    outro (ver CLAUDE.md — domínios isolados)."""
    if not regions:
        return []

    def _list_region(region: str) -> list[tuple[str, str]]:
        sql = f"""
            SELECT table_schema AS dataset_id, table_name AS table_id
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.TABLES`
        """
        rows = client.query(sql).result()
        return [(row.dataset_id, row.table_id) for row in rows]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_list_region, regions))
    return [ref for region_refs in results for ref in region_refs]
