"""Só fala com o Cloud Logging — extrai eventos de job completado do
BigQuery a partir de audit logs (Data Access, categoria opcional —
precisa estar habilitada no projeto alvo; ver domains/access/service.py
sobre o aviso devolvido quando o resultado vem vazio).

Duplica (não importa) a lógica de parsing de domains/lineage/
repository.py — nenhum domínio deste projeto importa de outro (ver
CLAUDE.md, domínios isolados). Diferença: aqui o evento carrega também
o timestamp de conclusão do job (job.jobStatistics.endTime), necessário
pra "quando" — lineage não precisa disso.

Mesmo formato de payload validado em domains/lineage/repository.py
(legado AuditData/jobCompletedEvent, não BigQueryAuditMetadata/
jobChange).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from google.api_core.exceptions import Forbidden
from google.cloud import logging as cloud_logging

from observability_hub.core.exceptions import LoggingAccessDeniedError

LOOKBACK_DAYS = 30
_PAGE_SIZE = 1000

TableRefTuple = tuple[str, str, str]  # (project_id, dataset_id, table_id)


@dataclass(frozen=True)
class AccessEvent:
    job_id: str
    principal_email: str
    timestamp: datetime | None
    referenced_tables: list[TableRefTuple]
    destination_table: TableRefTuple | None


def _parse_table_ref(ref: dict | None) -> TableRefTuple | None:
    if not ref:
        return None
    project_id = ref.get("projectId")
    dataset_id = ref.get("datasetId")
    table_id = ref.get("tableId")
    if not project_id or not dataset_id or not table_id:
        return None
    return project_id, dataset_id, table_id


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_entry(entry: cloud_logging.LogEntry) -> AccessEvent | None:
    payload = entry.payload if isinstance(entry.payload, dict) else None
    if payload is None:
        return None

    job = payload.get("serviceData", {}).get("jobCompletedEvent", {}).get("job", {})
    if not job:
        return None

    job_stats = job.get("jobStatistics", {})
    raw_referenced = job_stats.get("referencedTables", [])
    referenced = [ref for r in raw_referenced if (ref := _parse_table_ref(r)) is not None]
    timestamp = _parse_timestamp(job_stats.get("endTime"))

    job_config = job.get("jobConfiguration", {})
    destination_raw = job_config.get("query", {}).get("destinationTable") or job_config.get(
        "load", {}
    ).get("destinationTable")
    destination = _parse_table_ref(destination_raw)
    if destination is not None and destination[1].startswith("_"):
        # Dataset anônimo do BigQuery (cache de resultado de query
        # interativa sem destino explícito) — não é uma escrita real,
        # mesma convenção de domains/lineage/repository.py.
        destination = None

    job_name = job.get("jobName", {})
    job_id = job_name.get("jobId", "") if isinstance(job_name, dict) else ""
    principal_email = payload.get("authenticationInfo", {}).get("principalEmail", "")

    return AccessEvent(
        job_id=job_id,
        principal_email=principal_email,
        timestamp=timestamp,
        referenced_tables=referenced,
        destination_table=destination,
    )


def list_access_events(client: cloud_logging.Client, project_id: str) -> list[AccessEvent]:
    """Levanta LoggingAccessDeniedError se a SA de runtime não tiver
    roles/logging.viewer no projeto. Lista vazia (sem erro) é o resultado
    tanto de "nenhum job rodou na janela" quanto de "Data Access audit
    logs desabilitados" — indistinguível por aqui, ver aviso estático em
    domains/access/service.py.

    Só cobre acessos originados por jobs que rodaram NESTE projeto — um
    job rodando em outro projeto que referencia uma tabela deste projeto
    (leitura cross-project) não aparece aqui, porque o audit log dele
    vive no projeto onde o job rodou, não no projeto da tabela lida (ver
    docs/specs/access.md, "Casos de borda")."""
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
    except Forbidden as exc:
        raise LoggingAccessDeniedError(project_id) from exc
