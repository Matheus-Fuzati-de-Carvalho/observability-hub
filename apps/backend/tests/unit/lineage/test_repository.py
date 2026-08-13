from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import PermissionDenied

from observability_hub.core.exceptions import LoggingAccessDeniedError
from observability_hub.domains.lineage import repository


def _entry(payload: dict | None):
    return SimpleNamespace(payload=payload)


# --- _parse_table_ref --------------------------------------------------------


def test_parse_table_ref_valid_format():
    result = repository._parse_table_ref("projects/proj/datasets/RAW/tables/crm_leads")
    assert result == ("proj", "RAW", "crm_leads")


@pytest.mark.parametrize(
    "ref",
    [None, "", "not-a-table-ref", "projects/proj/datasets/RAW", "projects/proj/tables/crm_leads"],
)
def test_parse_table_ref_returns_none_for_malformed_input(ref):
    assert repository._parse_table_ref(ref) is None


# --- _parse_entry -------------------------------------------------------------


def test_parse_entry_extracts_referenced_and_destination_tables():
    payload = {
        "authenticationInfo": {"principalEmail": "a@dp6.com.br"},
        "metadata": {
            "jobChange": {
                "job": {
                    "jobName": "projects/proj/jobs/job123/location/US",
                    "jobConfig": {
                        "queryConfig": {
                            "destinationTable": "projects/proj/datasets/GOLD/tables/leads_summary",
                        }
                    },
                    "jobStats": {
                        "queryStats": {
                            "referencedTables": [
                                "projects/proj/datasets/RAW/tables/crm_leads",
                                "projects/proj/datasets/RAW/tables/crm_accounts",
                            ]
                        }
                    },
                }
            }
        },
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.job_id == "job123"
    assert event.principal_email == "a@dp6.com.br"
    assert event.destination_table == ("proj", "GOLD", "leads_summary")
    assert set(event.referenced_tables) == {
        ("proj", "RAW", "crm_leads"),
        ("proj", "RAW", "crm_accounts"),
    }


def test_parse_entry_falls_back_to_load_config_destination():
    payload = {
        "metadata": {
            "jobChange": {
                "job": {
                    "jobName": "projects/proj/jobs/job456/location/US",
                    "jobConfig": {
                        "loadConfig": {
                            "destinationTable": "projects/proj/datasets/RAW/tables/crm_leads",
                        }
                    },
                    "jobStats": {"queryStats": {}},
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.destination_table == ("proj", "RAW", "crm_leads")
    assert event.referenced_tables == []


def test_parse_entry_returns_none_when_payload_is_not_a_dict():
    assert repository._parse_entry(_entry(None)) is None
    assert repository._parse_entry(_entry("not a dict")) is None


def test_parse_entry_returns_none_when_job_change_missing():
    assert repository._parse_entry(_entry({"metadata": {}})) is None
    assert repository._parse_entry(_entry({})) is None


def test_parse_entry_skips_malformed_referenced_table_entries():
    payload = {
        "metadata": {
            "jobChange": {
                "job": {
                    "jobName": "",
                    "jobStats": {
                        "queryStats": {
                            "referencedTables": [
                                "projects/proj/datasets/RAW/tables/crm_leads",
                                "garbage",
                            ]
                        }
                    },
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.referenced_tables == [("proj", "RAW", "crm_leads")]


# --- list_job_events -----------------------------------------------------------


def test_list_job_events_raises_logging_access_denied():
    client = MagicMock()
    client.list_entries.side_effect = PermissionDenied("denied")

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_job_events(client, "observability-hub-dev")


def test_list_job_events_raises_when_permission_denied_during_iteration():
    """PermissionDenied costuma só estourar ao iterar (list_entries devolve
    um iterador preguiçoso) — não só na chamada inicial."""

    def _raise_on_iter():
        raise PermissionDenied("denied")
        yield  # pragma: no cover

    client = MagicMock()
    client.list_entries.return_value = _raise_on_iter()

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_job_events(client, "observability-hub-dev")


def test_list_job_events_parses_valid_entries_and_skips_invalid_ones():
    valid_payload = {
        "metadata": {
            "jobChange": {
                "job": {
                    "jobName": "projects/proj/jobs/job1/location/US",
                    "jobStats": {"queryStats": {"referencedTables": []}},
                }
            }
        }
    }
    client = MagicMock()
    client.list_entries.return_value = [_entry(valid_payload), _entry(None)]

    events = repository.list_job_events(client, "observability-hub-dev")

    assert len(events) == 1
    assert events[0].job_id == "job1"
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
            result.result.return_value = [
                SimpleNamespace(dataset_id="RAW", table_id="crm_leads"),
            ]
        else:
            result.result.return_value = [
                SimpleNamespace(dataset_id="RAW", table_id="crm_accounts"),
            ]
        return result

    client.query.side_effect = _query

    refs = repository.list_all_table_refs(client, "proj", ["US", "EU"])

    assert set(refs) == {("RAW", "crm_leads"), ("RAW", "crm_accounts")}
