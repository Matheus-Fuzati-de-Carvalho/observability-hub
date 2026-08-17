"""Orquestra as analytics de uso/gestão do Hub (login, favoritos entre
usuários, atividade de profiling, navegação agregada, scans de PII,
solicitações de acesso) — api/v1/admin.py e api/v1/auth.py só chamam
estas funções. CLAUDE.md proíbe lógica de negócio em api/.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from google.cloud import firestore

from observability_hub.domains.admin import analytics_repository as repository
from observability_hub.domains.admin import repository as acl_repository
from observability_hub.domains.admin.analytics_schemas import (
    AccessRequestAnalyticsResponse,
    AccessRequestMonthBucket,
    FavoriteEntry,
    FavoritesAnalyticsResponse,
    LoginAnalyticsResponse,
    LoginCountBucket,
    LoginEvent,
    NavigationAnalyticsResponse,
    PiiScanActivityResponse,
    PiiScanEntry,
    ProfilingActivityResponse,
    ProfilingRunEntry,
    ProjectRequestCount,
    SearchEntry,
    TableViewEntry,
)

logger = logging.getLogger(__name__)

_RECENT_LOGIN_EVENTS_LIMIT = 50


def record_login(client: firestore.Client, email: str) -> None:
    """Best-effort: login é o caminho crítico, uma falha aqui nunca pode
    impedir o usuário de entrar. Erro só é logado, nunca propagado."""
    try:
        repository.record_login(client, email, datetime.now(UTC))
    except Exception:
        logger.warning("falha ao gravar login_event para %s", email, exc_info=True)


def _bucket_key(dt: datetime, granularity: str) -> str:
    if granularity == "daily":
        return dt.strftime("%Y-%m-%d")
    if granularity == "weekly":
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return dt.strftime("%Y-%m")


def _bucket_events(events: list[dict], granularity: str) -> list[LoginCountBucket]:
    emails_by_period: dict[str, set[str]] = defaultdict(set)
    counts_by_period: dict[str, int] = defaultdict(int)
    for event in events:
        period = _bucket_key(event["logged_in_at"], granularity)
        counts_by_period[period] += 1
        emails_by_period[period].add(event["email"])

    return [
        LoginCountBucket(
            period=period,
            login_count=counts_by_period[period],
            unique_users=len(emails_by_period[period]),
        )
        for period in sorted(counts_by_period)
    ]


def get_login_analytics(
    client: firestore.Client, lookback_days: int = 90
) -> LoginAnalyticsResponse:
    since = datetime.now(UTC) - timedelta(days=lookback_days)
    events = repository.list_login_events(client, since)

    return LoginAnalyticsResponse(
        daily=_bucket_events(events, "daily"),
        weekly=_bucket_events(events, "weekly"),
        monthly=_bucket_events(events, "monthly"),
        recent_events=[LoginEvent(**e) for e in events[:_RECENT_LOGIN_EVENTS_LIMIT]],
    )


def get_favorites_analytics(client: firestore.Client) -> FavoritesAnalyticsResponse:
    raw = repository.list_all_favorites(client)
    raw.sort(key=lambda f: f["added_at"], reverse=True)
    return FavoritesAnalyticsResponse(favorites=[FavoriteEntry(**f) for f in raw])


def get_profiling_activity(client: firestore.Client, limit: int = 200) -> ProfilingActivityResponse:
    raw = repository.list_all_profiling_runs(client)
    # Runs gravados antes do acréscimo de project_id/dataset_id/table_id
    # (ver domains/quality/history_repository.py) não têm esses campos —
    # saem sozinhos da janela quando o cap de 30/tabela rotacionar, sem
    # precisar de backfill.
    valid = [r for r in raw if "project_id" in r]
    valid.sort(key=lambda r: r["executed_at"], reverse=True)
    return ProfilingActivityResponse(runs=[ProfilingRunEntry(**r) for r in valid[:limit]])


_MONTH_BUCKET_DEFAULT = {"total": 0, "approved": 0, "denied": 0, "pending": 0}


def get_access_request_analytics(client: firestore.Client) -> AccessRequestAnalyticsResponse:
    raw = acl_repository.list_access_requests(client)

    monthly: dict[str, dict[str, int]] = defaultdict(lambda: dict(_MONTH_BUCKET_DEFAULT))
    project_counts: dict[str, int] = defaultdict(int)
    approved = denied = 0
    for r in raw:
        period = r["requested_at"].strftime("%Y-%m")
        monthly[period]["total"] += 1
        monthly[period][r["status"]] += 1
        project_counts[r["project_id"]] += 1
        if r["status"] == "approved":
            approved += 1
        elif r["status"] == "denied":
            denied += 1

    resolved = approved + denied
    approval_rate = round(approved / resolved * 100, 1) if resolved else None

    monthly_buckets = [
        AccessRequestMonthBucket(period=period, **counts)
        for period, counts in sorted(monthly.items())
    ]
    top_projects = sorted(
        (
            ProjectRequestCount(project_id=project_id, request_count=count)
            for project_id, count in project_counts.items()
        ),
        key=lambda p: p.request_count,
        reverse=True,
    )[:10]

    return AccessRequestAnalyticsResponse(
        monthly=monthly_buckets, top_projects=top_projects, approval_rate=approval_rate
    )


def get_navigation_analytics(client: firestore.Client) -> NavigationAnalyticsResponse:
    table_views = repository.list_all_table_views(client)
    searches = repository.list_all_searches(client)
    return NavigationAnalyticsResponse(
        table_views=[TableViewEntry(**v) for v in table_views],
        searches=[SearchEntry(**s) for s in searches],
    )


def get_pii_scan_activity(client: firestore.Client, limit: int = 200) -> PiiScanActivityResponse:
    raw = repository.list_all_pii_scans(client)
    raw.sort(key=lambda r: r["executed_at"], reverse=True)
    return PiiScanActivityResponse(scans=[PiiScanEntry(**r) for r in raw[:limit]])
