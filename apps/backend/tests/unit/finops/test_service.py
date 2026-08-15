from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from observability_hub.domains.finops import service
from observability_hub.domains.finops.repository import ScanEvent


def _fake_client() -> MagicMock:
    return MagicMock(name="bigquery.Client")


def _now() -> datetime:
    # Sempre lido na hora, nunca uma constante fixa — o service também
    # calcula datetime.now(UTC) na hora de rodar, então usar um valor fixo
    # aqui criaria um desvio (por menor que fosse) entre o "agora" do
    # teste e o "agora" do service, e o teste ficaria refém da data real
    # em que roda.
    return datetime.now(UTC)


def _bq_table(
    num_bytes=2_000_000_000,
    num_rows=1_000_000,
    modified=None,
    time_partitioning=None,
    range_partitioning=None,
):
    return SimpleNamespace(
        num_bytes=num_bytes,
        num_rows=num_rows,
        modified=modified,
        time_partitioning=time_partitioning,
        range_partitioning=range_partitioning,
    )


def _stub_common(monkeypatch, all_tables, metadata):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(service.repository, "list_all_table_refs", lambda *a, **kw: all_tables)
    monkeypatch.setattr(service, "get_tables_metadata", lambda client, refs: metadata)


def _event(referenced, timestamp, total_billed_bytes=0):
    return ScanEvent(
        timestamp=timestamp, referenced_tables=referenced, total_billed_bytes=total_billed_bytes
    )


# --- scan_unused_tables ----------------------------------------------------------


def test_scan_unused_tables_flags_table_never_accessed(monkeypatch):
    _stub_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": _bq_table()},
    )
    monkeypatch.setattr(
        service.repository, "list_scan_events", lambda *a, **kw: [_event([], _now())]
    )

    result = service.scan_unused_tables(_fake_client(), MagicMock(), "proj")

    assert len(result.tables) == 1
    assert result.tables[0].table_id == "crm_leads"
    assert result.tables[0].days_since_last_access is None
    assert result.tables[0].last_accessed_at is None


def test_scan_unused_tables_excludes_recently_accessed_table(monkeypatch):
    _stub_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": _bq_table()},
    )
    recent = _now() - timedelta(days=5)
    events = [_event([("proj", "RAW", "crm_leads")], recent)]
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: events)

    result = service.scan_unused_tables(_fake_client(), MagicMock(), "proj", min_days_unused=30)

    assert result.tables == []


def test_scan_unused_tables_includes_table_accessed_exactly_at_threshold(monkeypatch):
    _stub_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": _bq_table()},
    )
    exactly_30d_ago = _now() - timedelta(days=30)
    events = [_event([("proj", "RAW", "crm_leads")], exactly_30d_ago)]
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: events)

    result = service.scan_unused_tables(_fake_client(), MagicMock(), "proj", min_days_unused=30)

    assert len(result.tables) == 1
    assert result.tables[0].days_since_last_access == 30


def test_scan_unused_tables_ignores_events_from_other_projects(monkeypatch):
    _stub_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": _bq_table()},
    )
    events = [_event([("other-proj", "RAW", "crm_leads")], _now() - timedelta(days=1))]
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: events)

    result = service.scan_unused_tables(_fake_client(), MagicMock(), "proj")

    assert len(result.tables) == 1
    assert result.tables[0].days_since_last_access is None


def test_scan_unused_tables_uses_active_storage_price_for_recently_modified_table(monkeypatch):
    modified = _now() - timedelta(days=10)  # dentro de 90d -> active
    _stub_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": _bq_table(num_bytes=1024**3, modified=modified)},  # 1 GB
    )
    monkeypatch.setattr(
        service.repository, "list_scan_events", lambda *a, **kw: [_event([], _now())]
    )

    result = service.scan_unused_tables(_fake_client(), MagicMock(), "proj")

    assert (
        result.tables[0].estimated_monthly_storage_cost_usd
        == service.settings.bigquery_storage_price_usd_per_gb_month_active
    )


def test_scan_unused_tables_uses_long_term_storage_price_for_old_table(monkeypatch):
    modified = _now() - timedelta(days=120)  # 90+ dias -> long-term
    _stub_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": _bq_table(num_bytes=1024**3, modified=modified)},
    )
    monkeypatch.setattr(
        service.repository, "list_scan_events", lambda *a, **kw: [_event([], _now())]
    )

    result = service.scan_unused_tables(_fake_client(), MagicMock(), "proj")

    assert (
        result.tables[0].estimated_monthly_storage_cost_usd
        == service.settings.bigquery_storage_price_usd_per_gb_month_long_term
    )


def test_scan_unused_tables_sets_warning_when_no_events(monkeypatch):
    _stub_common(monkeypatch, all_tables=[], metadata={})
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: [])

    result = service.scan_unused_tables(_fake_client(), MagicMock(), "proj")

    assert result.warning is not None
    assert "proj" in result.warning


def test_scan_unused_tables_adds_retention_caveat_for_windows_above_30_days(monkeypatch):
    _stub_common(monkeypatch, all_tables=[], metadata={})
    monkeypatch.setattr(
        service.repository, "list_scan_events", lambda *a, **kw: [_event([], _now())]
    )

    result_30 = service.scan_unused_tables(_fake_client(), MagicMock(), "proj", min_days_unused=30)
    result_60 = service.scan_unused_tables(_fake_client(), MagicMock(), "proj", min_days_unused=60)

    assert result_30.warning is None
    assert result_60.warning is not None
    assert "retenção" in result_60.warning


def test_scan_unused_tables_skips_table_missing_from_metadata(monkeypatch):
    _stub_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": None},
    )
    monkeypatch.setattr(
        service.repository, "list_scan_events", lambda *a, **kw: [_event([], _now())]
    )

    result = service.scan_unused_tables(_fake_client(), MagicMock(), "proj")

    assert result.tables == []


# --- scan_partition_candidates ----------------------------------------------------


def _stub_partition_common(monkeypatch, all_tables, metadata, date_columns_by_table=None):
    _stub_common(monkeypatch, all_tables, metadata)
    monkeypatch.setattr(
        service, "resolve_dataset_region", lambda client, project_id, dataset_id, regions: "US"
    )
    date_columns_by_table = date_columns_by_table or {}
    monkeypatch.setattr(
        service.repository,
        "get_date_like_columns",
        lambda client, project_id, dataset_id, table_id, location: date_columns_by_table.get(
            (dataset_id, table_id), []
        ),
    )


def test_scan_partition_candidates_excludes_small_tables(monkeypatch):
    _stub_partition_common(
        monkeypatch,
        all_tables=[("RAW", "small_table")],
        metadata={"proj.RAW.small_table": _bq_table(num_bytes=1000)},
    )
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: [])

    result = service.scan_partition_candidates(_fake_client(), MagicMock(), "proj")

    assert result.candidates == []


def test_scan_partition_candidates_excludes_already_partitioned_tables(monkeypatch):
    _stub_partition_common(
        monkeypatch,
        all_tables=[("RAW", "big_table")],
        metadata={
            "proj.RAW.big_table": _bq_table(
                num_bytes=2_000_000_000, time_partitioning=SimpleNamespace(field="event_date")
            )
        },
    )
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: [])

    result = service.scan_partition_candidates(_fake_client(), MagicMock(), "proj")

    assert result.candidates == []


def test_scan_partition_candidates_excludes_tables_without_date_like_column(monkeypatch):
    _stub_partition_common(
        monkeypatch,
        all_tables=[("RAW", "big_table")],
        metadata={"proj.RAW.big_table": _bq_table(num_bytes=2_000_000_000)},
        date_columns_by_table={},
    )
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: [])

    result = service.scan_partition_candidates(_fake_client(), MagicMock(), "proj")

    assert result.candidates == []


def test_scan_partition_candidates_includes_candidate_with_observed_cost_and_savings_range(
    monkeypatch,
):
    _stub_partition_common(
        monkeypatch,
        all_tables=[("RAW", "big_table")],
        metadata={"proj.RAW.big_table": _bq_table(num_bytes=2_000_000_000)},
        date_columns_by_table={("RAW", "big_table"): ["event_date"]},
    )
    events = [_event([("proj", "RAW", "big_table")], _now(), total_billed_bytes=10**12)]
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: events)

    result = service.scan_partition_candidates(_fake_client(), MagicMock(), "proj")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.candidate_partition_columns == ["event_date"]
    assert candidate.observed_billed_bytes_30d == 10**12
    assert candidate.observed_cost_usd_30d > 0
    assert candidate.estimated_savings_usd_conservative == round(
        candidate.observed_cost_usd_30d * 0.30, 6
    )
    assert candidate.estimated_savings_usd_optimistic == round(
        candidate.observed_cost_usd_30d * 0.70, 6
    )
    assert candidate.savings_disclaimer is not None


def test_scan_partition_candidates_no_savings_estimate_without_observed_cost(monkeypatch):
    _stub_partition_common(
        monkeypatch,
        all_tables=[("RAW", "big_table")],
        metadata={"proj.RAW.big_table": _bq_table(num_bytes=2_000_000_000)},
        date_columns_by_table={("RAW", "big_table"): ["event_date"]},
    )
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: [])

    result = service.scan_partition_candidates(_fake_client(), MagicMock(), "proj")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.observed_billed_bytes_30d == 0
    assert candidate.estimated_savings_usd_conservative is None
    assert candidate.estimated_savings_usd_optimistic is None
    assert candidate.savings_disclaimer is None


def test_scan_partition_candidates_resolves_region_once_per_dataset(monkeypatch):
    _stub_partition_common(
        monkeypatch,
        all_tables=[("RAW", "table_a"), ("RAW", "table_b")],
        metadata={
            "proj.RAW.table_a": _bq_table(num_bytes=2_000_000_000),
            "proj.RAW.table_b": _bq_table(num_bytes=2_000_000_000),
        },
        date_columns_by_table={("RAW", "table_a"): ["d"], ("RAW", "table_b"): ["d"]},
    )
    resolve_mock = MagicMock(return_value="US")
    monkeypatch.setattr(service, "resolve_dataset_region", resolve_mock)
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: [])

    result = service.scan_partition_candidates(_fake_client(), MagicMock(), "proj")

    assert len(result.candidates) == 2
    assert resolve_mock.call_count == 1


def test_scan_partition_candidates_sorts_by_observed_cost_descending(monkeypatch):
    _stub_partition_common(
        monkeypatch,
        all_tables=[("RAW", "cheap"), ("RAW", "expensive")],
        metadata={
            "proj.RAW.cheap": _bq_table(num_bytes=2_000_000_000),
            "proj.RAW.expensive": _bq_table(num_bytes=2_000_000_000),
        },
        date_columns_by_table={("RAW", "cheap"): ["d"], ("RAW", "expensive"): ["d"]},
    )
    events = [
        _event([("proj", "RAW", "cheap")], _now(), total_billed_bytes=10**9),
        _event([("proj", "RAW", "expensive")], _now(), total_billed_bytes=10**13),
    ]
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: events)

    result = service.scan_partition_candidates(_fake_client(), MagicMock(), "proj")

    assert [c.table_id for c in result.candidates] == ["expensive", "cheap"]
