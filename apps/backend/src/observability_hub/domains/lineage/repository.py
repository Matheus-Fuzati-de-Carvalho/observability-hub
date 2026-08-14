"""Só fala com o Cloud Logging — extrai eventos de job completado do
BigQuery a partir de audit logs (Data Access, categoria opcional —
precisa estar habilitada no projeto alvo; ver domains/lineage/service.py
sobre o aviso devolvido quando o resultado vem vazio).

Formato do payload validado contra logs reais de observability-hub-dev
(2026-08-14): o projeto emite o formato legado `AuditData`/
`jobCompletedEvent` (`google.cloud.bigquery.logging.v1.AuditData`), não
o formato novo `BigQueryAuditMetadata`/`jobChange` descrito em
https://docs.cloud.google.com/bigquery/docs/reference/auditlogs/migration
— a doc de migração descreve o destino da migração, não o formato
efetivamente em uso aqui. `referencedTables`/`destinationTable` vêm como
dicts `{projectId, datasetId, tableId}`, não como strings
`"projects/.../datasets/.../tables/..."`.
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


def _parse_table_ref(ref: dict | None) -> TableRefTuple | None:
    """{"projectId": p, "datasetId": d, "tableId": t} -> (p, d, t); None se
    algum campo obrigatório faltar (defensivo — não deve travar o parsing
    de um job inteiro por causa de uma referência inesperada)."""
    if not ref:
        return None
    project_id = ref.get("projectId")
    dataset_id = ref.get("datasetId")
    table_id = ref.get("tableId")
    if not project_id or not dataset_id or not table_id:
        return None
    return project_id, dataset_id, table_id


def _parse_entry(entry: cloud_logging.LogEntry) -> JobEvent | None:
    payload = entry.payload if isinstance(entry.payload, dict) else None
    if payload is None:
        return None

    job = payload.get("serviceData", {}).get("jobCompletedEvent", {}).get("job", {})
    if not job:
        return None

    job_stats = job.get("jobStatistics", {})
    raw_referenced = job_stats.get("referencedTables", [])
    referenced = [ref for r in raw_referenced if (ref := _parse_table_ref(r)) is not None]

    job_config = job.get("jobConfiguration", {})
    destination_raw = job_config.get("query", {}).get("destinationTable") or job_config.get(
        "load", {}
    ).get("destinationTable")
    destination = _parse_table_ref(destination_raw)

    job_name = job.get("jobName", {})
    job_id = job_name.get("jobId", "") if isinstance(job_name, dict) else ""
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
