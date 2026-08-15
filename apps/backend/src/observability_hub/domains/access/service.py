"""Orquestra o domínio access: cruza os jobs completados (Cloud Logging,
via repository) pra descobrir quem acessou uma tabela e quando. api/v1
só chama estas funções — CLAUDE.md proíbe lógica de negócio em api/.
"""

from google.cloud import logging as cloud_logging

from observability_hub.core.bigquery import get_client
from observability_hub.domains.access import repository
from observability_hub.domains.access.repository import TableRefTuple
from observability_hub.domains.access.schemas import TableAccessEntry, TableAccessResponse

_EMPTY_RESULT_WARNING = (
    "Nenhum evento de job encontrado nos audit logs dos últimos {days} dias. "
    "Isso pode significar (a) que não houve atividade na janela, (b) que os "
    "Data Access audit logs estão desabilitados no projeto '{project_id}' "
    "(mapa de acesso depende deles — Admin Activity logs, sempre ativos, não "
    "bastam) ou (c) que a service account do Hub tem roles/logging.viewer "
    "mas não roles/logging.privateLogViewer no projeto — Data Access audit "
    "logs só ficam visíveis via API com a segunda role, mesmo com a "
    "primeira concedida (a chamada não falha, só retorna vazio). Verifique "
    "auditConfigs com: gcloud projects get-iam-policy {project_id} "
    "--format=json (procure por 'auditConfigs' com service "
    "'bigquery.googleapis.com'); verifique as duas roles da SA com o mesmo "
    "comando, procurando por 'logging.viewer' e 'logging.privateLogViewer'."
)

_DEFAULT_LIMIT = 20


def _empty_result_warning(project_id: str) -> str:
    return _EMPTY_RESULT_WARNING.format(days=repository.LOOKBACK_DAYS, project_id=project_id)


def _is_service_account(principal_email: str) -> bool:
    return principal_email.endswith("gserviceaccount.com")


def _hub_runtime_sa_email() -> str:
    """SA de runtime do próprio Hub (Cloud Run, ver core/bigquery.py::
    get_client() e o mesmo padrão em main.py::handle_project_access_denied) —
    excluída do mapa de acesso porque toda vez que o usuário roda
    profiling/PII numa tabela pela UI, é essa SA (não o usuário) quem
    executa a query real no BigQuery. Sem esse filtro, o próprio ato de
    inspecionar uma tabela pelo Hub apareceria como "acesso recente" —
    ruído, não um consumidor real de fora."""
    runtime_project = get_client().project
    return f"backend-run@{runtime_project}.iam.gserviceaccount.com"


def get_table_access(
    logging_client: cloud_logging.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    limit: int = _DEFAULT_LIMIT,
) -> TableAccessResponse:
    target: TableRefTuple = (project_id, dataset_id, table_id)
    events = repository.list_access_events(logging_client, project_id)
    hub_sa_email = _hub_runtime_sa_email()

    by_principal: dict[str, dict] = {}
    for event in events:
        if event.timestamp is None:
            continue  # sem "quando" não é útil pro mapa de acesso
        if event.principal_email == hub_sa_email:
            continue  # o próprio Hub rodando profiling/PII não é um acesso externo real

        types: set[str] = set()
        if target in event.referenced_tables:
            types.add("read")
        if event.destination_table == target:
            types.add("write")
        if not types:
            continue

        entry = by_principal.setdefault(
            event.principal_email,
            {"last_accessed_at": event.timestamp, "access_count": 0, "access_types": set()},
        )
        entry["access_count"] += 1
        entry["access_types"] |= types
        entry["last_accessed_at"] = max(entry["last_accessed_at"], event.timestamp)

    users = [
        TableAccessEntry(
            principal_email=principal,
            is_service_account=_is_service_account(principal),
            last_accessed_at=data["last_accessed_at"],
            access_count=data["access_count"],
            access_types=sorted(data["access_types"]),
        )
        for principal, data in by_principal.items()
    ]
    users.sort(key=lambda u: u.last_accessed_at, reverse=True)

    return TableAccessResponse(
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        lookback_days=repository.LOOKBACK_DAYS,
        users=users[:limit],
        warning=_empty_result_warning(project_id) if not events else None,
    )
