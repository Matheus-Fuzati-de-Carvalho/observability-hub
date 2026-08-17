from datetime import UTC, datetime
from unittest.mock import MagicMock

from observability_hub.domains.admin import analytics_service as service


def test_record_login_delegates_to_repository(monkeypatch):
    client = MagicMock()
    captured = {}

    def fake_record_login(client, email, now):
        captured.update(email=email, now=now)

    monkeypatch.setattr(service.repository, "record_login", fake_record_login)

    service.record_login(client, "a@dp6.com.br")

    assert captured["email"] == "a@dp6.com.br"
    assert isinstance(captured["now"], datetime)


def test_record_login_swallows_repository_errors(monkeypatch):
    client = MagicMock()

    def fake_record_login(client, email, now):
        raise RuntimeError("firestore indisponível")

    monkeypatch.setattr(service.repository, "record_login", fake_record_login)

    # Não deve levantar — login nunca pode falhar por causa de analytics.
    service.record_login(client, "a@dp6.com.br")


def test_get_login_analytics_buckets_by_day_week_month(monkeypatch):
    client = MagicMock()
    events = [
        {"email": "a@dp6.com.br", "logged_in_at": datetime(2026, 8, 17, 9, tzinfo=UTC)},
        {"email": "b@dp6.com.br", "logged_in_at": datetime(2026, 8, 17, 14, tzinfo=UTC)},
        {"email": "a@dp6.com.br", "logged_in_at": datetime(2026, 8, 10, 9, tzinfo=UTC)},
    ]
    monkeypatch.setattr(service.repository, "list_login_events", lambda client, since: events)

    result = service.get_login_analytics(client, lookback_days=30)

    daily_by_period = {b.period: b for b in result.daily}
    assert daily_by_period["2026-08-17"].login_count == 2
    assert daily_by_period["2026-08-17"].unique_users == 2
    assert daily_by_period["2026-08-10"].login_count == 1

    monthly_by_period = {b.period: b for b in result.monthly}
    assert monthly_by_period["2026-08"].login_count == 3
    assert monthly_by_period["2026-08"].unique_users == 2

    assert len(result.recent_events) == 3


def test_get_login_analytics_recent_events_capped_at_50(monkeypatch):
    client = MagicMock()
    events = [
        {"email": f"user{i}@dp6.com.br", "logged_in_at": datetime(2026, 8, 17, tzinfo=UTC)}
        for i in range(60)
    ]
    monkeypatch.setattr(service.repository, "list_login_events", lambda client, since: events)

    result = service.get_login_analytics(client)

    assert len(result.recent_events) == 50


def test_get_favorites_analytics_wraps_and_sorts_by_added_at_desc(monkeypatch):
    client = MagicMock()
    raw = [
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "nickname": None,
            "owner_email": "a@dp6.com.br",
            "added_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": None,
            "nickname": "Minha base",
            "owner_email": "b@dp6.com.br",
            "added_at": datetime(2026, 6, 1, tzinfo=UTC),
        },
    ]
    monkeypatch.setattr(service.repository, "list_all_favorites", lambda client: raw)

    result = service.get_favorites_analytics(client)

    assert [f.owner_email for f in result.favorites] == ["b@dp6.com.br", "a@dp6.com.br"]


def test_get_profiling_activity_filters_runs_without_project_id(monkeypatch):
    client = MagicMock()
    raw = [
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "executed_by": "a@dp6.com.br",
            "executed_at": datetime(2026, 8, 17, tzinfo=UTC),
            "overall_density": 90.0,
            "estimated_duplicate_pct": 1.0,
        },
        # Run antigo, gravado antes do acréscimo de project_id/dataset_id/table_id.
        {
            "executed_by": "a@dp6.com.br",
            "executed_at": datetime(2026, 1, 1, tzinfo=UTC),
            "overall_density": 80.0,
            "estimated_duplicate_pct": 2.0,
        },
    ]
    monkeypatch.setattr(service.repository, "list_all_profiling_runs", lambda client: raw)

    result = service.get_profiling_activity(client)

    assert len(result.runs) == 1
    assert result.runs[0].project_id == "proj"


def test_get_profiling_activity_sorts_desc_and_limits(monkeypatch):
    client = MagicMock()
    raw = [
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": f"t{i}",
            "executed_by": "a@dp6.com.br",
            "executed_at": datetime(2026, 1, i + 1, tzinfo=UTC),
            "overall_density": 90.0,
            "estimated_duplicate_pct": 1.0,
        }
        for i in range(5)
    ]
    monkeypatch.setattr(service.repository, "list_all_profiling_runs", lambda client: raw)

    result = service.get_profiling_activity(client, limit=2)

    assert len(result.runs) == 2
    assert result.runs[0].table_id == "t4"
    assert result.runs[1].table_id == "t3"


def test_get_access_request_analytics_buckets_by_month_and_status(monkeypatch):
    client = MagicMock()
    raw = [
        {
            "project_id": "proj-a",
            "status": "approved",
            "requested_at": datetime(2026, 8, 1, tzinfo=UTC),
        },
        {
            "project_id": "proj-a",
            "status": "denied",
            "requested_at": datetime(2026, 8, 5, tzinfo=UTC),
        },
        {
            "project_id": "proj-b",
            "status": "pending",
            "requested_at": datetime(2026, 7, 1, tzinfo=UTC),
        },
    ]
    monkeypatch.setattr(service.acl_repository, "list_access_requests", lambda client: raw)

    result = service.get_access_request_analytics(client)

    monthly_by_period = {b.period: b for b in result.monthly}
    assert monthly_by_period["2026-08"].total == 2
    assert monthly_by_period["2026-08"].approved == 1
    assert monthly_by_period["2026-08"].denied == 1
    assert monthly_by_period["2026-07"].pending == 1

    top_project_ids = [p.project_id for p in result.top_projects]
    assert top_project_ids == ["proj-a", "proj-b"]
    assert result.approval_rate == 50.0


def test_get_access_request_analytics_approval_rate_none_when_nothing_resolved(monkeypatch):
    client = MagicMock()
    raw = [
        {
            "project_id": "proj-a",
            "status": "pending",
            "requested_at": datetime(2026, 8, 1, tzinfo=UTC),
        },
    ]
    monkeypatch.setattr(service.acl_repository, "list_access_requests", lambda client: raw)

    result = service.get_access_request_analytics(client)

    assert result.approval_rate is None


def test_get_navigation_analytics_wraps_table_views_and_searches(monkeypatch):
    client = MagicMock()
    table_views = [
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "owner_email": "a@dp6.com.br",
            "viewed_at": datetime(2026, 8, 17, tzinfo=UTC),
        }
    ]
    searches = [
        {
            "query": "crm_leads",
            "mode": "table",
            "project_id": "proj",
            "owner_email": "a@dp6.com.br",
            "searched_at": datetime(2026, 8, 17, tzinfo=UTC),
        }
    ]
    monkeypatch.setattr(service.repository, "list_all_table_views", lambda client: table_views)
    monkeypatch.setattr(service.repository, "list_all_searches", lambda client: searches)

    result = service.get_navigation_analytics(client)

    assert len(result.table_views) == 1
    assert result.table_views[0].table_id == "events"
    assert len(result.searches) == 1
    assert result.searches[0].query == "crm_leads"


def test_get_pii_scan_activity_sorts_desc_and_limits(monkeypatch):
    client = MagicMock()
    raw = [
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": f"t{i}",
            "executed_by": "a@dp6.com.br",
            "executed_at": datetime(2026, 1, i + 1, tzinfo=UTC),
            "flagged_columns_count": i,
        }
        for i in range(5)
    ]
    monkeypatch.setattr(service.repository, "list_all_pii_scans", lambda client: raw)

    result = service.get_pii_scan_activity(client, limit=2)

    assert len(result.scans) == 2
    assert result.scans[0].table_id == "t4"
    assert result.scans[1].table_id == "t3"
