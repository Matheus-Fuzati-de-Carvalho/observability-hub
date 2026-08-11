import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core.exceptions import ProjectAccessDeniedError
from observability_hub.domains.quality import repository


def _row(**kwargs):
    return SimpleNamespace(**kwargs)


def test_to_jsonable_scalar_passes_through_json_native_types():
    assert repository._to_jsonable_scalar(None) is None
    assert repository._to_jsonable_scalar(True) is True
    assert repository._to_jsonable_scalar(42) == 42
    assert repository._to_jsonable_scalar(3.14) == 3.14
    assert repository._to_jsonable_scalar("lead") == "lead"


def test_to_jsonable_scalar_converts_decimal_to_string():
    assert repository._to_jsonable_scalar(Decimal("12.50")) == "12.50"


def test_to_jsonable_scalar_converts_date_to_isoformat():
    assert repository._to_jsonable_scalar(dt.date(2026, 1, 15)) == "2026-01-15"


def test_to_jsonable_scalar_converts_datetime_to_isoformat():
    value = dt.datetime(2026, 1, 15, 10, 30, tzinfo=dt.UTC)
    assert repository._to_jsonable_scalar(value) == value.isoformat()


def test_get_table_columns_maps_is_nullable_and_data_type():
    rows = [
        _row(column_name="lead_status", data_type="STRING", is_nullable="YES"),
        _row(column_name="id", data_type="INT64", is_nullable="NO"),
    ]
    client = MagicMock()
    client.query.return_value.result.return_value = rows

    result = repository.get_table_columns(client, "proj", "RAW", "leads", "US")

    assert result[0] == {"column_name": "lead_status", "data_type": "STRING", "is_nullable": True}
    assert result[1]["is_nullable"] is False


def test_is_view_true_for_view_table_type():
    client = MagicMock()
    client.query.return_value.result.return_value = [_row(table_type="VIEW")]

    assert repository.is_view(client, "proj", "RAW", "leads", "US") is True


def test_is_view_true_for_materialized_view_table_type():
    client = MagicMock()
    client.query.return_value.result.return_value = [_row(table_type="MATERIALIZED VIEW")]

    assert repository.is_view(client, "proj", "RAW", "leads", "US") is True


def test_is_view_false_for_base_table_type():
    client = MagicMock()
    client.query.return_value.result.return_value = [_row(table_type="BASE TABLE")]

    assert repository.is_view(client, "proj", "RAW", "leads", "US") is False


def test_is_view_false_when_no_rows_found():
    client = MagicMock()
    client.query.return_value.result.return_value = []

    assert repository.is_view(client, "proj", "RAW", "ghost", "US") is False


def test_get_total_table_rows_returns_value_when_present():
    client = MagicMock()
    client.query.return_value.result.return_value = [_row(total_rows=10000)]

    result = repository.get_total_table_rows(client, "proj", "RAW", "leads", "US")

    assert result == 10000


def test_get_total_table_rows_returns_none_when_not_in_table_storage_yet():
    client = MagicMock()
    client.query.return_value.result.return_value = []

    result = repository.get_total_table_rows(client, "proj", "RAW", "leads", "US")

    assert result is None


def test_dry_run_uses_dry_run_job_config_and_returns_bytes():
    captured = {}

    def fake_query(sql, job_config=None):
        captured["job_config"] = job_config
        return SimpleNamespace(total_bytes_processed=849813)

    client = MagicMock()
    client.query.side_effect = fake_query

    result = repository.dry_run(client, "proj", "SELECT 1")

    assert result == 849813
    assert captured["job_config"].dry_run is True


def test_dry_run_raises_project_access_denied_on_forbidden():
    client = MagicMock()
    client.query.side_effect = Forbidden("Access Denied")

    with pytest.raises(ProjectAccessDeniedError) as exc_info:
        repository.dry_run(client, "proj", "SELECT 1")

    assert exc_info.value.project_id == "proj"


def test_execute_main_query_converts_row_values_to_jsonable_scalars():
    row = {
        "_total_sampled_rows": 10000,
        "_approx_distinct_rows": 9526,
        "lead_status__min": "lead",
        "lead_status__max": "venda_concluida",
        "signup_date__min": dt.date(2026, 1, 1),
    }
    client = MagicMock()
    client.query.return_value.result.return_value = [row]

    result = repository.execute_main_query(client, "proj", "SELECT ...", timeout=60.0)

    assert result["_total_sampled_rows"] == 10000
    assert result["signup_date__min"] == "2026-01-01"


def test_execute_main_query_raises_project_access_denied_on_forbidden():
    client = MagicMock()
    client.query.side_effect = Forbidden("Access Denied")

    with pytest.raises(ProjectAccessDeniedError) as exc_info:
        repository.execute_main_query(client, "proj", "SELECT ...", timeout=60.0)

    assert exc_info.value.project_id == "proj"


def test_execute_top_n_query_returns_value_and_count():
    rows = [_row(value="lead", count=4200), _row(value="qualificado", count=3100)]
    client = MagicMock()
    client.query.return_value.result.return_value = rows

    result = repository.execute_top_n_query(client, "proj", "SELECT ...", timeout=60.0)

    assert result == [{"value": "lead", "count": 4200}, {"value": "qualificado", "count": 3100}]


def test_execute_top_n_query_raises_project_access_denied_on_forbidden():
    client = MagicMock()
    client.query.side_effect = Forbidden("Access Denied")

    with pytest.raises(ProjectAccessDeniedError) as exc_info:
        repository.execute_top_n_query(client, "proj", "SELECT ...", timeout=60.0)

    assert exc_info.value.project_id == "proj"


def test_execute_null_distribution_query_returns_period_null_count_total_rows():
    rows = [_row(period=dt.date(2026, 7, 1), null_count=0, total_rows=450)]
    client = MagicMock()
    client.query.return_value.result.return_value = rows

    result = repository.execute_null_distribution_query(client, "proj", "SELECT ...", timeout=60.0)

    assert result == [{"period": "2026-07-01", "null_count": 0, "total_rows": 450}]


def test_execute_null_distribution_query_raises_project_access_denied_on_forbidden():
    client = MagicMock()
    client.query.side_effect = Forbidden("Access Denied")

    with pytest.raises(ProjectAccessDeniedError) as exc_info:
        repository.execute_null_distribution_query(client, "proj", "SELECT ...", timeout=60.0)

    assert exc_info.value.project_id == "proj"
