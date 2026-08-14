"""Orquestra o domínio lineage: cruza os jobs completados (Cloud
Logging, via repository) pra reconstruir upstream/downstream de uma
tabela e a lista de órfãs de um projeto. api/v1 só chama estas funções —
CLAUDE.md proíbe lógica de negócio em api/.
"""

from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from observability_hub.core.bigquery import discover_regions
from observability_hub.domains.lineage import repository
from observability_hub.domains.lineage.schemas import (
    LineageResponse,
    OrphansResponse,
    OrphanTable,
    TableRef,
)

_EMPTY_RESULT_WARNING = (
    "Nenhum evento de job encontrado nos audit logs dos últimos {days} dias. "
    "Isso pode significar (a) que não houve atividade na janela, (b) que os "
    "Data Access audit logs estão desabilitados no projeto '{project_id}' "
    "(lineage depende deles — Admin Activity logs, sempre ativos, não "
    "bastam) ou (c) que a service account do Hub tem roles/logging.viewer "
    "mas não roles/logging.privateLogViewer no projeto — Data Access audit "
    "logs só ficam visíveis via API com a segunda role, mesmo com a "
    "primeira concedida (a chamada não falha, só retorna vazio). Verifique "
    "auditConfigs com: gcloud projects get-iam-policy {project_id} "
    "--format=json (procure por 'auditConfigs' com service "
    "'bigquery.googleapis.com'); verifique as duas roles da SA com o mesmo "
    "comando, procurando por 'logging.viewer' e 'logging.privateLogViewer'."
)


def _empty_result_warning(project_id: str) -> str:
    return _EMPTY_RESULT_WARNING.format(days=repository.LOOKBACK_DAYS, project_id=project_id)


def get_table_lineage(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
) -> LineageResponse:
    events = repository.list_job_events(logging_client, project_id)
    target = (dataset_id, table_id)

    upstream: set[tuple[str, str]] = set()
    downstream: set[tuple[str, str]] = set()
    for event in events:
        destination = event.destination_table
        wrote_target = destination is not None and destination[1:] == target
        read_target = any(ref[1:] == target for ref in event.referenced_tables)

        if wrote_target:
            upstream.update(ref[1:] for ref in event.referenced_tables if ref[1:] != target)
        if read_target and destination is not None and destination[1:] != target:
            downstream.add(destination[1:])

    return LineageResponse(
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        upstream=[
            TableRef(project_id=project_id, dataset_id=d, table_id=t) for d, t in sorted(upstream)
        ],
        downstream=[
            TableRef(project_id=project_id, dataset_id=d, table_id=t) for d, t in sorted(downstream)
        ],
        lookback_days=repository.LOOKBACK_DAYS,
        warning=_empty_result_warning(project_id) if not events else None,
    )


def get_orphans(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    project_id: str,
) -> OrphansResponse:
    regions = discover_regions(project_id, client=client)
    all_tables = repository.list_all_table_refs(client, project_id, regions)
    events = repository.list_job_events(logging_client, project_id)

    consumed: set[tuple[str, str]] = set()
    for event in events:
        for ref in event.referenced_tables:
            if ref[0] == project_id:
                consumed.add(ref[1:])

    orphans = sorted(t for t in all_tables if t not in consumed)

    return OrphansResponse(
        project_id=project_id,
        orphans=[OrphanTable(dataset_id=d, table_id=t) for d, t in orphans],
        lookback_days=repository.LOOKBACK_DAYS,
        warning=_empty_result_warning(project_id) if not events else None,
    )
