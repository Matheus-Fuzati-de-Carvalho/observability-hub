from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core.exceptions import LoggingAccessDeniedError, ProjectAccessDeniedError
from observability_hub.domains.finops import repository


def _row(**kwargs):
    return SimpleNamespace(**kwargs)


def _entry(payload: dict | None):
    return SimpleNamespace(payload=payload)


# --- _parse_table_ref --------------------------------------------------------


def test_parse_table_ref_valid_format():
    result = repository._parse_table_ref(
        {"projectId": "proj", "datasetId": "RAW", "tableId": "crm_leads"}
    )
    assert result == ("proj", "RAW", "crm_leads")


@pytest.mark.parametrize("ref", [None, {}, {"projectId": "proj", "datasetId": "RAW"}])
def test_parse_table_ref_returns_none_for_malformed_input(ref):
    assert repository._parse_table_ref(ref) is None


@pytest.mark.parametrize(
    "table_id",
    [
        "INFORMATION_SCHEMA.SCHEMATA",
        "INFORMATION_SCHEMA.TABLES",
        "INFORMATION_SCHEMA.TABLE_STORAGE",
    ],
)
def test_parse_table_ref_filters_information_schema_probes(table_id):
    # discover_regions/list_all_table_refs/get_date_like_columns do
    # próprio Hub rodam `project.region-X.INFORMATION_SCHEMA.*` — o audit
    # log real captura isso como datasetId="region-US" (ou outra região),
    # tableId="INFORMATION_SCHEMA.SCHEMATA" etc. Sem o filtro, isso
    # aparece como se "region-US" fosse um dataset real de cliente no
    # budget (bug real encontrado em dev).
    result = repository._parse_table_ref(
        {"projectId": "proj", "datasetId": "region-US", "tableId": table_id}
    )
    assert result is None


# --- _parse_timestamp / _parse_billed_bytes -------------------------------------


def test_parse_timestamp_parses_iso_with_z_suffix():
    from datetime import UTC, datetime

    assert repository._parse_timestamp("2026-08-14T14:33:05.199Z") == datetime(
        2026, 8, 14, 14, 33, 5, 199000, tzinfo=UTC
    )


@pytest.mark.parametrize("raw", [None, "", "not-a-date"])
def test_parse_timestamp_returns_none_for_missing_or_malformed_value(raw):
    assert repository._parse_timestamp(raw) is None


def test_parse_billed_bytes_parses_numeric_string():
    assert repository._parse_billed_bytes("10485760") == 10485760


@pytest.mark.parametrize("raw", [None, "", "not-a-number"])
def test_parse_billed_bytes_returns_zero_for_missing_or_malformed_value(raw):
    assert repository._parse_billed_bytes(raw) == 0


# --- _parse_entry -------------------------------------------------------------


def test_parse_entry_extracts_referenced_tables_timestamp_and_billed_bytes():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobStatistics": {
                        "endTime": "2026-08-14T14:33:05.199Z",
                        "totalBilledBytes": "10485760",
                        "referencedTables": [
                            {"projectId": "proj", "datasetId": "RAW", "tableId": "ga4_events"}
                        ],
                    }
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.referenced_tables == [("proj", "RAW", "ga4_events")]
    assert event.total_billed_bytes == 10485760
    assert event.timestamp is not None


def test_parse_entry_extracts_job_id_principal_and_query_text():
    payload = {
        "authenticationInfo": {"principalEmail": "ana@dp6.com.br"},
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job-123", "location": "US", "projectId": "proj"},
                    "jobConfiguration": {"query": {"query": "SELECT 1"}},
                    "jobStatistics": {"endTime": "2026-08-14T10:00:00Z", "referencedTables": []},
                }
            }
        },
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.job_id == "job-123"
    assert event.principal_email == "ana@dp6.com.br"
    assert event.query_text == "SELECT 1"


def test_parse_entry_truncates_long_query_text():
    long_query = "SELECT " + "x" * 3000
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobConfiguration": {"query": {"query": long_query}},
                    "jobStatistics": {"referencedTables": []},
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.query_text is not None
    assert len(event.query_text) == repository._QUERY_TEXT_MAX_CHARS + 1  # +1 do "…"
    assert event.query_text.endswith("…")


def test_parse_entry_query_text_is_none_when_missing():
    payload = {
        "serviceData": {"jobCompletedEvent": {"job": {"jobStatistics": {"referencedTables": []}}}}
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.query_text is None


def test_parse_entry_defaults_billed_bytes_to_zero_when_missing():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobStatistics": {"endTime": "2026-08-14T10:00:00Z", "referencedTables": []}
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.total_billed_bytes == 0


def test_parse_entry_returns_none_when_payload_is_not_a_dict():
    assert repository._parse_entry(_entry(None)) is None


def test_parse_entry_returns_none_when_job_completed_event_missing():
    assert repository._parse_entry(_entry({})) is None


# --- list_scan_events -----------------------------------------------------------


def test_list_scan_events_raises_logging_access_denied():
    client = MagicMock()
    client.list_entries.side_effect = Forbidden("denied")

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_scan_events(client, "observability-hub-dev", 30)


def test_list_scan_events_parses_valid_entries_and_skips_invalid_ones():
    valid_payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobStatistics": {"endTime": "2026-08-14T10:00:00Z", "referencedTables": []}
                }
            }
        }
    }
    client = MagicMock()
    client.list_entries.return_value = [_entry(valid_payload), _entry(None)]

    events = repository.list_scan_events(client, "observability-hub-dev", 30)

    assert len(events) == 1
    client.list_entries.assert_called_once()
    call_kwargs = client.list_entries.call_args.kwargs
    assert call_kwargs["resource_names"] == ["projects/observability-hub-dev"]
    assert 'resource.type="bigquery_resource"' in call_kwargs["filter_"]


# --- list_all_table_refs -------------------------------------------------------


def test_list_all_table_refs_returns_empty_for_no_regions():
    client = MagicMock()
    assert repository.list_all_table_refs(client, "proj", []) == []


def test_list_all_table_refs_merges_results_across_regions():
    client = MagicMock()

    def _query(sql):
        result = MagicMock()
        if "region-US" in sql:
            result.result.return_value = [SimpleNamespace(dataset_id="RAW", table_id="crm_leads")]
        else:
            result.result.return_value = [
                SimpleNamespace(dataset_id="RAW", table_id="crm_accounts")
            ]
        return result

    client.query.side_effect = _query

    refs = repository.list_all_table_refs(client, "proj", ["US", "EU"])

    assert set(refs) == {("RAW", "crm_leads"), ("RAW", "crm_accounts")}


# --- get_date_like_columns -------------------------------------------------------


def test_get_date_like_columns_returns_column_names():
    client = MagicMock()
    result = MagicMock()
    result.result.return_value = [
        SimpleNamespace(column_name="event_date"),
        SimpleNamespace(column_name="created_at"),
    ]
    client.query.return_value = result

    columns = repository.get_date_like_columns(client, "proj", "RAW", "crm_leads", "US")

    assert columns == ["event_date", "created_at"]
    call_args = client.query.call_args
    assert "INFORMATION_SCHEMA.COLUMNS" in call_args.args[0]
    job_config = call_args.kwargs["job_config"]
    param_names = {p.name for p in job_config.query_parameters}
    assert param_names == {"dataset_id", "table_id", "date_like_types"}


# --- get_string_columns -----------------------------------------------------------


def test_get_string_columns_returns_column_names():
    client = MagicMock()
    result = MagicMock()
    result.result.return_value = [
        _row(column_name="customer_id"),
        _row(column_name="signup_date_raw"),
    ]
    client.query.return_value = result

    columns = repository.get_string_columns(client, "proj", "RAW", "crm_leads", "US")

    assert columns == ["customer_id", "signup_date_raw"]
    call_args = client.query.call_args
    assert "INFORMATION_SCHEMA.COLUMNS" in call_args.args[0]
    assert "data_type = 'STRING'" in call_args.args[0]


def test_get_string_columns_returns_empty_list_when_no_string_columns():
    client = MagicMock()
    client.query.return_value.result.return_value = []

    assert repository.get_string_columns(client, "proj", "RAW", "crm_leads", "US") == []


# --- is_view (finops) -------------------------------------------------------------


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


# --- dry_run (finops) --------------------------------------------------------------


def test_dry_run_uses_dry_run_job_config_and_returns_bytes():
    captured = {}

    def fake_query(sql, job_config=None):
        captured["job_config"] = job_config
        return SimpleNamespace(total_bytes_processed=12345)

    client = MagicMock()
    client.query.side_effect = fake_query

    result = repository.dry_run(client, "proj", "SELECT 1")

    assert result == 12345
    assert captured["job_config"].dry_run is True


def test_dry_run_raises_project_access_denied_on_forbidden():
    client = MagicMock()
    client.query.side_effect = Forbidden("Access Denied")

    with pytest.raises(ProjectAccessDeniedError) as exc_info:
        repository.dry_run(client, "proj", "SELECT 1")

    assert exc_info.value.project_id == "proj"


# --- execute_scan_query (finops) ----------------------------------------------------


def test_execute_scan_query_returns_first_row_as_dict():
    row = {"customer_id__non_null": 950, "customer_id__INT64": 950}
    client = MagicMock()
    client.query.return_value.result.return_value = [row]

    result = repository.execute_scan_query(client, "proj", "SELECT ...", timeout=60.0)

    assert result == row


def test_execute_scan_query_raises_project_access_denied_on_forbidden():
    client = MagicMock()
    client.query.side_effect = Forbidden("Access Denied")

    with pytest.raises(ProjectAccessDeniedError) as exc_info:
        repository.execute_scan_query(client, "proj", "SELECT ...", timeout=60.0)

    assert exc_info.value.project_id == "proj"
