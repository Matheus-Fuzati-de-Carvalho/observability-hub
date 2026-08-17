import time as time_module
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import InvalidSamplePercentError
from observability_hub.domains.finops import service, sql_builder
from observability_hub.domains.finops.repository import ScanEvent
from observability_hub.domains.finops.schemas import (
    BudgetGroupBy,
    ColumnTypeScanRequest,
    SuggestedColumnType,
)


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


def _stub_column_type_common(
    monkeypatch, all_tables, metadata, view_tables=None, string_columns_by_table=None
):
    _stub_common(monkeypatch, all_tables, metadata)
    monkeypatch.setattr(
        service, "resolve_dataset_region", lambda client, project_id, dataset_id, regions: "US"
    )
    view_tables = view_tables or set()
    string_columns_by_table = string_columns_by_table or {}
    monkeypatch.setattr(
        service.repository,
        "is_view",
        lambda client, project_id, dataset_id, table_id, location: (
            (dataset_id, table_id) in view_tables
        ),
    )
    monkeypatch.setattr(
        service.repository,
        "get_string_columns",
        lambda client, project_id, dataset_id, table_id, location: string_columns_by_table.get(
            (dataset_id, table_id), []
        ),
    )


def _no_match_row(non_null=0):
    row = {"col__non_null": non_null, "col__avg_bytes": None}
    row.update({f"col__{t}": 0 for t in sql_builder.CANDIDATE_TYPES})
    return row


def _event(
    referenced,
    timestamp,
    total_billed_bytes=0,
    job_id="job1",
    principal_email="user@dp6.com.br",
    query_text=None,
):
    return ScanEvent(
        timestamp=timestamp,
        referenced_tables=referenced,
        total_billed_bytes=total_billed_bytes,
        job_id=job_id,
        principal_email=principal_email,
        query_text=query_text,
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


# --- get_budget --------------------------------------------------------------


def _stub_budget_events(monkeypatch, events):
    monkeypatch.setattr(service.repository, "list_scan_events", lambda *a, **kw: events)


def _last_day_of_previous_month():
    return _now().replace(day=1) - timedelta(days=1)


def test_get_budget_groups_by_table(monkeypatch):
    events = [
        _event([("proj", "RAW", "a"), ("proj", "TRUSTED", "b")], _now(), total_billed_bytes=10**12),
        _event([("proj", "RAW", "a")], _now(), total_billed_bytes=10**11),
    ]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj", group_by=BudgetGroupBy.TABLE)

    groups = {g.key: g for g in result.groups}
    assert set(groups) == {"proj.RAW.a", "proj.TRUSTED.b"}
    assert groups["proj.RAW.a"].billed_bytes == 10**12 + 10**11
    assert groups["proj.TRUSTED.b"].billed_bytes == 10**12
    assert groups["proj.RAW.a"].cost_usd > groups["proj.TRUSTED.b"].cost_usd


def test_get_budget_groups_by_user(monkeypatch):
    events = [
        _event(
            [("proj", "RAW", "a")],
            _now(),
            total_billed_bytes=10**9,
            principal_email="ana@dp6.com.br",
            job_id="job1",
        ),
        _event(
            [("proj", "RAW", "a")],
            _now(),
            total_billed_bytes=10**9,
            principal_email="ana@dp6.com.br",
            job_id="job2",
        ),
        _event(
            [("proj", "RAW", "a")],
            _now(),
            total_billed_bytes=10**13,
            principal_email="backend-run@proj.iam.gserviceaccount.com",
        ),
    ]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj", group_by=BudgetGroupBy.USER)

    groups = {g.key: g for g in result.groups}
    assert groups["ana@dp6.com.br"].job_count == 2
    assert groups["ana@dp6.com.br"].billed_bytes == 2 * 10**9
    assert groups["backend-run@proj.iam.gserviceaccount.com"].billed_bytes == 10**13
    # ordenado por custo desc
    assert result.groups[0].key == "backend-run@proj.iam.gserviceaccount.com"


def test_get_budget_groups_by_day(monkeypatch):
    now = _now()
    events = [
        _event([("proj", "RAW", "a")], now, total_billed_bytes=10**9),
        _event([("proj", "RAW", "a")], now, total_billed_bytes=10**9),
    ]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj", group_by=BudgetGroupBy.DAY)

    assert len(result.groups) == 1
    assert result.groups[0].key == now.date().isoformat()
    assert result.groups[0].job_count == 2


def test_get_budget_groups_by_month(monkeypatch):
    now = _now()
    events = [_event([("proj", "RAW", "a")], now, total_billed_bytes=10**9)]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj", group_by=BudgetGroupBy.MONTH)

    assert result.groups[0].key == now.strftime("%Y-%m")


def test_get_budget_groups_by_year(monkeypatch):
    now = _now()
    events = [_event([("proj", "RAW", "a")], now, total_billed_bytes=10**9)]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj", group_by=BudgetGroupBy.YEAR)

    assert result.groups[0].key == str(now.year)


def test_get_budget_skips_events_with_no_real_table_information_schema_only(monkeypatch):
    # referenced_tables já vem filtrado de INFORMATION_SCHEMA por
    # repository._parse_table_ref — aqui simula o caso em que um evento
    # só referenciava tabelas fora do projeto (equivalente a "nenhuma
    # tabela real restou"), que get_budget deve pular por completo (não
    # entra em groups nem em top_queries), reproduzindo o bug real de
    # "region-US" sendo contado como dataset fantasma.
    events = [_event([("other-proj", "RAW", "a")], _now(), total_billed_bytes=10**12)]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj")

    assert result.groups == []
    assert result.top_queries == []
    assert result.total_cost_usd == 0


def test_get_budget_ranks_top_queries_by_cost(monkeypatch):
    events = [
        _event([("proj", "RAW", "a")], _now(), total_billed_bytes=10**9, job_id="cheap-job"),
        _event([("proj", "RAW", "b")], _now(), total_billed_bytes=10**13, job_id="expensive-job"),
    ]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj")

    assert [q.job_id for q in result.top_queries] == ["expensive-job", "cheap-job"]


def test_get_budget_includes_query_text_and_tables_in_top_queries(monkeypatch):
    events = [
        _event(
            [("proj", "RAW", "a")],
            _now(),
            total_billed_bytes=10**9,
            job_id="job1",
            query_text="SELECT * FROM a",
        )
    ]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj")

    assert result.top_queries[0].query_text == "SELECT * FROM a"
    assert result.top_queries[0].tables == ["proj.RAW.a"]


def test_get_budget_ignores_zero_cost_events(monkeypatch):
    events = [_event([("proj", "RAW", "a")], _now(), total_billed_bytes=0)]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj")

    assert result.groups == []
    assert result.top_queries == []


def test_get_budget_ignores_events_before_month_start(monkeypatch):
    events = [
        _event([("proj", "RAW", "a")], _last_day_of_previous_month(), total_billed_bytes=10**12)
    ]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj")

    assert result.groups == []


def test_get_budget_ignores_events_from_other_projects(monkeypatch):
    events = [_event([("other-proj", "RAW", "a")], _now(), total_billed_bytes=10**12)]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj")

    assert result.groups == []


def test_get_budget_respects_limit(monkeypatch):
    events = [
        _event(
            [("proj", "RAW", "a")],
            _now(),
            total_billed_bytes=10**9 * (i + 1),
            job_id=f"job{i}",
            principal_email=f"user{i}@dp6.com.br",
        )
        for i in range(5)
    ]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj", limit=2)

    assert len(result.top_queries) == 2


def test_get_budget_computes_projection(monkeypatch):
    events = [_event([("proj", "RAW", "a")], _now(), total_billed_bytes=10**12)]
    _stub_budget_events(monkeypatch, events)

    result = service.get_budget(MagicMock(), "proj")

    assert result.projection.days_elapsed == result.lookback_days
    assert result.projection.days_in_month >= result.projection.days_elapsed
    assert result.projection.cost_so_far_usd > 0
    assert result.projection.daily_average_usd == round(
        result.projection.cost_so_far_usd / result.projection.days_elapsed, 6
    )
    # projected_month_total_usd é derivado do daily_average NÃO arredondado
    # (mais preciso) — comparar contra o daily_average já arredondado da
    # resposta dá uma diferença de poucos milionésimos, por isso a
    # tolerância em vez de igualdade exata.
    assert result.projection.projected_month_total_usd == pytest.approx(
        result.projection.daily_average_usd * result.projection.days_in_month, abs=1e-4
    )
    assert result.projection.projected_month_total_usd >= result.projection.cost_so_far_usd


def test_get_budget_sets_warning_when_no_events(monkeypatch):
    _stub_budget_events(monkeypatch, [])

    result = service.get_budget(MagicMock(), "proj")

    assert result.warning is not None
    assert "proj" in result.warning


# --- _pick_suggestion ----------------------------------------------------------


def test_pick_suggestion_returns_none_when_no_non_null_sampled_values():
    assert service._pick_suggestion("col", _no_match_row(non_null=0), row_count=1_000_000) is None


def test_pick_suggestion_returns_none_when_no_candidate_type_matches_fully():
    row = _no_match_row(non_null=100)
    row["col__INT64"] = 80  # não bateu em 100% dos valores não-nulos

    assert service._pick_suggestion("col", row, row_count=1_000_000) is None


def test_pick_suggestion_picks_int64_before_float64_when_both_match():
    row = _no_match_row(non_null=100)
    row["col__avg_bytes"] = 10.0  # avg_current_bytes = 12.0 > 8 (INT64) -> economiza
    row["col__INT64"] = 100
    row["col__FLOAT64"] = 100  # todo INT64 também bate em FLOAT64 -- INT64 deve vencer

    result = service._pick_suggestion("col", row, row_count=1_000_000)

    assert result is not None
    assert result.suggested_type == SuggestedColumnType.INT64
    assert result.sample_non_null_count == 100
    assert result.avg_current_bytes == 12.0
    assert result.suggested_type_bytes == 8
    assert result.estimated_storage_savings_usd_month > 0


def test_pick_suggestion_falls_back_to_float64_when_int64_does_not_fully_match():
    row = _no_match_row(non_null=100)
    row["col__avg_bytes"] = 10.0
    row["col__INT64"] = 90  # alguns valores são decimais
    row["col__FLOAT64"] = 100

    result = service._pick_suggestion("col", row, row_count=1_000_000)

    assert result is not None
    assert result.suggested_type == SuggestedColumnType.FLOAT64


def test_pick_suggestion_picks_bool_when_only_bool_matches():
    row = _no_match_row(non_null=100)
    row["col__avg_bytes"] = 5.0  # avg_current_bytes = 7.0 > 1 (BOOL) -> economiza
    row["col__BOOL"] = 100

    result = service._pick_suggestion("col", row, row_count=1_000_000)

    assert result is not None
    assert result.suggested_type == SuggestedColumnType.BOOL


def test_pick_suggestion_returns_none_when_string_already_smaller_than_suggested_type():
    row = _no_match_row(non_null=100)
    row["col__avg_bytes"] = 0.5  # avg_current_bytes = 2.5 <= 8 (INT64) -> não economiza
    row["col__INT64"] = 100

    assert service._pick_suggestion("col", row, row_count=1_000_000) is None


# --- estimate_column_type_suggestions -------------------------------------------


def test_estimate_column_type_suggestions_raises_for_invalid_sample_percent():
    with pytest.raises(InvalidSamplePercentError):
        service.estimate_column_type_suggestions(
            _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=0)
        )


def test_estimate_column_type_suggestions_sums_dry_run_bytes_across_eligible_tables(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "a"), ("RAW", "b")],
        metadata={
            "proj.RAW.a": _bq_table(num_rows=1000),
            "proj.RAW.b": _bq_table(num_rows=1000),
        },
        string_columns_by_table={("RAW", "a"): ["col"], ("RAW", "b"): ["col1", "col2"]},
    )
    monkeypatch.setattr(service.repository, "dry_run", lambda client, project_id, sql: 1000)

    result = service.estimate_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10)
    )

    assert result.tables_scanned == 2
    assert result.columns_scanned == 3  # 1 + 2
    assert result.estimated_bytes == 2000  # 1000 por tabela
    assert result.tables_skipped_view == 0


def test_estimate_column_type_suggestions_skips_views_without_dry_run(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "a_view")],
        metadata={"proj.RAW.a_view": _bq_table(num_rows=1000)},
        view_tables={("RAW", "a_view")},
        string_columns_by_table={("RAW", "a_view"): ["col"]},
    )
    dry_run_mock = MagicMock(return_value=1000)
    monkeypatch.setattr(service.repository, "dry_run", dry_run_mock)

    result = service.estimate_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10)
    )

    assert result.tables_scanned == 0
    assert result.tables_skipped_view == 1
    assert result.estimated_bytes == 0
    dry_run_mock.assert_not_called()


def test_estimate_column_type_suggestions_skips_tables_without_string_columns(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "numeric_only")],
        metadata={"proj.RAW.numeric_only": _bq_table(num_rows=1000)},
        string_columns_by_table={},  # nenhuma coluna STRING
    )

    result = service.estimate_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10)
    )

    assert result.tables_scanned == 0
    assert result.tables_skipped_view == 0


# --- run_column_type_suggestions -------------------------------------------------


def test_run_column_type_suggestions_raises_for_invalid_sample_percent():
    with pytest.raises(InvalidSamplePercentError):
        service.run_column_type_suggestions(
            _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=0)
        )


def test_run_column_type_suggestions_returns_candidate_with_suggestion(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": _bq_table(num_rows=1_000_000, num_bytes=5_000_000_000)},
        string_columns_by_table={("RAW", "crm_leads"): ["customer_id"]},
    )
    row = {
        "customer_id__non_null": 950,
        "customer_id__avg_bytes": 10.0,
        **{f"customer_id__{t}": 0 for t in sql_builder.CANDIDATE_TYPES},
    }
    row["customer_id__INT64"] = 950
    monkeypatch.setattr(
        service.repository, "execute_scan_query", lambda client, project_id, sql, timeout: row
    )

    result = service.run_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10)
    )

    assert result.tables_scanned == 1
    assert result.tables_skipped_view == 0
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.dataset_id == "RAW"
    assert candidate.table_id == "crm_leads"
    assert candidate.row_count == 1_000_000
    assert len(candidate.suggestions) == 1
    assert candidate.suggestions[0].column_name == "customer_id"
    assert candidate.suggestions[0].suggested_type == SuggestedColumnType.INT64
    assert result.warning is None


def test_run_column_type_suggestions_excludes_table_with_no_viable_suggestion(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "crm_leads")],
        metadata={"proj.RAW.crm_leads": _bq_table(num_rows=1000)},
        string_columns_by_table={("RAW", "crm_leads"): ["col"]},
    )
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _no_match_row(non_null=100),
    )

    result = service.run_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10)
    )

    assert result.tables_scanned == 1
    assert result.candidates == []


def test_run_column_type_suggestions_skips_views(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "a_view")],
        metadata={"proj.RAW.a_view": _bq_table(num_rows=1000)},
        view_tables={("RAW", "a_view")},
        string_columns_by_table={("RAW", "a_view"): ["col"]},
    )
    execute_mock = MagicMock()
    monkeypatch.setattr(service.repository, "execute_scan_query", execute_mock)

    result = service.run_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10)
    )

    assert result.tables_scanned == 0
    assert result.tables_skipped_view == 1
    assert result.candidates == []
    execute_mock.assert_not_called()


def test_run_column_type_suggestions_sorts_candidates_by_total_savings_descending(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "small_savings"), ("RAW", "big_savings")],
        metadata={
            "proj.RAW.small_savings": _bq_table(num_rows=1_000),
            "proj.RAW.big_savings": _bq_table(num_rows=100_000_000),
        },
        string_columns_by_table={
            ("RAW", "small_savings"): ["col"],
            ("RAW", "big_savings"): ["col"],
        },
    )

    def fake_execute(client, project_id, sql, timeout):
        row = {
            "col__non_null": 100,
            "col__avg_bytes": 10.0,
            **{f"col__{t}": 0 for t in sql_builder.CANDIDATE_TYPES},
        }
        row["col__INT64"] = 100
        return row

    monkeypatch.setattr(service.repository, "execute_scan_query", fake_execute)

    result = service.run_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10)
    )

    assert [c.table_id for c in result.candidates] == ["big_savings", "small_savings"]


def test_run_column_type_suggestions_returns_partial_result_when_time_budget_exhausted(
    monkeypatch,
):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "a"), ("RAW", "b")],
        metadata={
            "proj.RAW.a": _bq_table(num_rows=1000),
            "proj.RAW.b": _bq_table(num_rows=1000),
        },
        string_columns_by_table={("RAW", "a"): ["col"], ("RAW", "b"): ["col"]},
    )
    monkeypatch.setattr(service, "_COLUMN_TYPE_SCAN_TIMEOUT_SECONDS", 0.01)

    def slow_execute(client, project_id, sql, timeout):
        time_module.sleep(0.3)
        return _no_match_row(non_null=0)

    monkeypatch.setattr(service.repository, "execute_scan_query", slow_execute)

    result = service.run_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10)
    )

    assert result.warning is not None
    assert "parcial" in result.warning


# --- escopo (tables) -------------------------------------------------------------


def test_parse_scoped_tables_splits_dataset_and_table_on_first_dot():
    assert service._parse_scoped_tables(["RAW.crm_leads", "TRUSTED.orders"]) == [
        ("RAW", "crm_leads"),
        ("TRUSTED", "orders"),
    ]


def test_parse_scoped_tables_skips_malformed_entries():
    assert service._parse_scoped_tables(["no_dot_here", "RAW.", ".table", ""]) == []


def test_estimate_column_type_suggestions_with_scope_skips_list_all_table_refs(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "a"), ("RAW", "b"), ("TRUSTED", "c")],
        metadata={
            "proj.RAW.a": _bq_table(num_rows=1000),
            "proj.RAW.b": _bq_table(num_rows=1000),
            "proj.TRUSTED.c": _bq_table(num_rows=1000),
        },
        string_columns_by_table={
            ("RAW", "a"): ["col"],
            ("RAW", "b"): ["col"],
            ("TRUSTED", "c"): ["col"],
        },
    )
    list_all_mock = MagicMock(side_effect=AssertionError("não deveria enumerar o projeto todo"))
    monkeypatch.setattr(service.repository, "list_all_table_refs", list_all_mock)
    monkeypatch.setattr(service.repository, "dry_run", lambda client, project_id, sql: 1000)

    result = service.estimate_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10, tables=["RAW.a"])
    )

    assert result.tables_scanned == 1
    list_all_mock.assert_not_called()


def test_run_column_type_suggestions_with_scope_only_scans_requested_tables(monkeypatch):
    _stub_column_type_common(
        monkeypatch,
        all_tables=[("RAW", "a"), ("RAW", "b")],
        metadata={
            "proj.RAW.a": _bq_table(num_rows=1_000_000),
            "proj.RAW.b": _bq_table(num_rows=1_000_000),
        },
        string_columns_by_table={("RAW", "a"): ["col"], ("RAW", "b"): ["col"]},
    )

    def fake_execute(client, project_id, sql, timeout):
        row = {
            "col__non_null": 100,
            "col__avg_bytes": 10.0,
            **{f"col__{t}": 0 for t in sql_builder.CANDIDATE_TYPES},
        }
        row["col__INT64"] = 100
        return row

    monkeypatch.setattr(service.repository, "execute_scan_query", fake_execute)

    result = service.run_column_type_suggestions(
        _fake_client(), "proj", ColumnTypeScanRequest(sample_percent=10, tables=["RAW.a"])
    )

    assert result.tables_scanned == 1
    assert [c.table_id for c in result.candidates] == ["a"]
