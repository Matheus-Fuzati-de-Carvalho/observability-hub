"""Orquestra o domínio lineage: cruza os jobs completados (Cloud
Logging, via repository) pra reconstruir a cadeia transitiva de
upstream/downstream de uma tabela (grafo, BFS bidirecional — ver
docs/specs/lineage.md) e a lista de órfãs de um projeto. api/v1 só chama
estas funções — CLAUDE.md proíbe lógica de negócio em api/.
"""

from typing import Literal

from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from observability_hub.core.bigquery import discover_regions
from observability_hub.core.exceptions import LoggingAccessDeniedError
from observability_hub.domains.lineage import repository
from observability_hub.domains.lineage.repository import JobEvent, TableRefTuple
from observability_hub.domains.lineage.schemas import (
    LineageEdge,
    LineageGraphResponse,
    LineageNode,
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

_MAX_HOPS_DEFAULT = 8


def _empty_result_warning(project_id: str) -> str:
    return _EMPTY_RESULT_WARNING.format(days=repository.LOOKBACK_DAYS, project_id=project_id)


def _node_id(ref: TableRefTuple) -> str:
    return f"{ref[0]}:{ref[1]}:{ref[2]}"


def _get_project_events(
    logging_client: cloud_logging.Client,
    project_id: str,
    events_cache: dict[str, list[JobEvent]],
    denied_projects: set[str],
) -> list[JobEvent] | None:
    """None => projeto sem acesso de Logging (soft-fail) — chamador não
    deve expandir a partir de nós desse projeto. No máximo uma chamada a
    repository.list_job_events por projeto por requisição (events_cache/
    denied_projects são compartilhados pelas duas direções da travessia)."""
    if project_id in denied_projects:
        return None
    if project_id in events_cache:
        return events_cache[project_id]
    try:
        events = repository.list_job_events(logging_client, project_id)
    except LoggingAccessDeniedError:
        denied_projects.add(project_id)
        return None
    events_cache[project_id] = events
    return events


def _traverse(
    logging_client: cloud_logging.Client,
    root: TableRefTuple,
    root_events: list[JobEvent],
    direction: Literal["upstream", "downstream"],
    max_hops: int,
    events_cache: dict[str, list[JobEvent]],
    denied_projects: set[str],
) -> tuple[dict[TableRefTuple, LineageNode], dict[tuple[str, str], LineageEdge], bool]:
    """BFS a partir de root, só nessa direção. Um nó já visitado não é
    reexpandido, mas a aresta que fecha um ciclo sobre ele ainda é
    registrada (cycle-safe sem perder a aresta)."""
    sign = -1 if direction == "upstream" else 1
    visited: dict[TableRefTuple, int] = {root: 0}
    nodes: dict[TableRefTuple, LineageNode] = {}
    edges: dict[tuple[str, str], LineageEdge] = {}

    frontier: list[tuple[TableRefTuple, list[JobEvent]]] = [(root, root_events)]
    hop = 0
    truncated = False

    while frontier:
        if hop >= max_hops:
            truncated = True
            break

        next_frontier: list[tuple[TableRefTuple, list[JobEvent]]] = []
        for table_ref, events in frontier:
            for event in events:
                if direction == "upstream":
                    if event.destination_table != table_ref:
                        continue
                    candidates = event.referenced_tables
                else:
                    if table_ref not in event.referenced_tables:
                        continue
                    candidates = [event.destination_table] if event.destination_table else []

                for neighbor in candidates:
                    if neighbor is None or neighbor == table_ref:
                        continue  # auto-referência (ex: MERGE), nunca vira aresta

                    source, target = (
                        (neighbor, table_ref) if direction == "upstream" else (table_ref, neighbor)
                    )
                    edge_key = (_node_id(source), _node_id(target))
                    edges.setdefault(
                        edge_key,
                        LineageEdge(source=edge_key[0], target=edge_key[1], job_id=event.job_id),
                    )

                    if neighbor in visited:
                        continue

                    next_hop = hop + 1
                    visited[neighbor] = next_hop
                    neighbor_events = _get_project_events(
                        logging_client, neighbor[0], events_cache, denied_projects
                    )
                    if neighbor_events is None:
                        nodes[neighbor] = LineageNode(
                            id=_node_id(neighbor),
                            project_id=neighbor[0],
                            dataset_id=neighbor[1],
                            table_id=neighbor[2],
                            hop_distance=sign * next_hop,
                            is_root=False,
                            access_denied=True,
                        )
                        continue

                    nodes[neighbor] = LineageNode(
                        id=_node_id(neighbor),
                        project_id=neighbor[0],
                        dataset_id=neighbor[1],
                        table_id=neighbor[2],
                        hop_distance=sign * next_hop,
                        is_root=False,
                        access_denied=False,
                    )
                    next_frontier.append((neighbor, neighbor_events))

        frontier = next_frontier
        hop += 1

    return nodes, edges, truncated


def get_table_lineage(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    max_hops: int = _MAX_HOPS_DEFAULT,
) -> LineageGraphResponse:
    root: TableRefTuple = (project_id, dataset_id, table_id)
    root_events = repository.list_job_events(logging_client, project_id)

    events_cache: dict[str, list[JobEvent]] = {project_id: root_events}
    denied_projects: set[str] = set()

    upstream_nodes, upstream_edges, upstream_truncated = _traverse(
        logging_client, root, root_events, "upstream", max_hops, events_cache, denied_projects
    )
    downstream_nodes, downstream_edges, downstream_truncated = _traverse(
        logging_client, root, root_events, "downstream", max_hops, events_cache, denied_projects
    )

    merged_nodes: dict[TableRefTuple, LineageNode] = dict(upstream_nodes)
    for ref, node in downstream_nodes.items():
        existing = merged_nodes.get(ref)
        if existing is None or abs(node.hop_distance) < abs(existing.hop_distance):
            merged_nodes[ref] = node

    merged_edges: dict[tuple[str, str], LineageEdge] = dict(upstream_edges)
    for key, edge in downstream_edges.items():
        merged_edges.setdefault(key, edge)

    nodes = sorted(merged_nodes.values(), key=lambda n: (n.hop_distance, n.id))
    edges = sorted(merged_edges.values(), key=lambda e: (e.source, e.target))

    return LineageGraphResponse(
        root=TableRef(project_id=project_id, dataset_id=dataset_id, table_id=table_id),
        nodes=nodes,
        edges=edges,
        lookback_days=repository.LOOKBACK_DAYS,
        max_hops=max_hops,
        truncated=upstream_truncated or downstream_truncated,
        warning=_empty_result_warning(project_id) if not root_events else None,
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
