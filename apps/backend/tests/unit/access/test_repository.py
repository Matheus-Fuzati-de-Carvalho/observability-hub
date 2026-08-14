from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core.exceptions import LoggingAccessDeniedError
from observability_hub.domains.access import repository


def _entry(payload: dict | None):
    return SimpleNamespace(payload=payload)


# Mesmo payload real capturado em domains/lineage/tests, ver docstring de
# repository.py — reaproveitado aqui pra validar também o parsing de
# endTime (jobStatistics.endTime), que lineage não precisa.
REAL_CTAS_PROTO_PAYLOAD = {
    "authenticationInfo": {
        "oauthInfo": {"oauthClientId": "32555940559.apps.googleusercontent.com"},
        "principalEmail": "fuzatimatheus.cloud@gmail.com",
    },
    "methodName": "jobservice.jobcompleted",
    "serviceData": {
        "jobCompletedEvent": {
            "eventName": "query_job_completed",
            "job": {
                "jobConfiguration": {
                    "query": {
                        "destinationTable": {
                            "datasetId": "TRUSTED",
                            "projectId": "observability-hub-dev",
                            "tableId": "ga4_sessions",
                        },
                        "statementType": "CREATE_TABLE_AS_SELECT",
                    }
                },
                "jobName": {
                    "jobId": "bqjob_r5bf5dfa96120dc26_000001a000b0cfae_1",
                    "location": "US",
                    "projectId": "observability-hub-dev",
                },
                "jobStatistics": {
                    "createTime": "2026-08-14T14:33:03.171Z",
                    "endTime": "2026-08-14T14:33:05.199Z",
                    "referencedTables": [
                        {
                            "datasetId": "RAW",
                            "projectId": "observability-hub-dev",
                            "tableId": "ga4_events",
                        }
                    ],
                },
                "jobStatus": {"error": {}, "state": "DONE"},
            },
        }
    },
    "serviceName": "bigquery.googleapis.com",
}


# --- _parse_table_ref --------------------------------------------------------


def test_parse_table_ref_valid_format():
    result = repository._parse_table_ref(
        {"projectId": "proj", "datasetId": "RAW", "tableId": "crm_leads"}
    )
    assert result == ("proj", "RAW", "crm_leads")


@pytest.mark.parametrize(
    "ref",
    [
        None,
        {},
        {"projectId": "proj", "datasetId": "RAW"},
        {"projectId": "proj", "tableId": "crm_leads"},
        {"datasetId": "RAW", "tableId": "crm_leads"},
    ],
)
def test_parse_table_ref_returns_none_for_malformed_input(ref):
    assert repository._parse_table_ref(ref) is None


# --- _parse_timestamp ----------------------------------------------------------


def test_parse_timestamp_parses_iso_with_z_suffix():
    result = repository._parse_timestamp("2026-08-14T14:33:05.199Z")
    assert result == datetime(2026, 8, 14, 14, 33, 5, 199000, tzinfo=UTC)


@pytest.mark.parametrize("raw", [None, ""])
def test_parse_timestamp_returns_none_for_missing_value(raw):
    assert repository._parse_timestamp(raw) is None


def test_parse_timestamp_returns_none_for_malformed_value():
    assert repository._parse_timestamp("not-a-date") is None


# --- _parse_entry -------------------------------------------------------------


def test_parse_entry_extracts_fields_and_timestamp_from_real_payload():
    event = repository._parse_entry(_entry(REAL_CTAS_PROTO_PAYLOAD))

    assert event is not None
    assert event.job_id == "bqjob_r5bf5dfa96120dc26_000001a000b0cfae_1"
    assert event.principal_email == "fuzatimatheus.cloud@gmail.com"
    assert event.destination_table == ("observability-hub-dev", "TRUSTED", "ga4_sessions")
    assert event.referenced_tables == [("observability-hub-dev", "RAW", "ga4_events")]
    assert event.timestamp == datetime(2026, 8, 14, 14, 33, 5, 199000, tzinfo=UTC)


def test_parse_entry_treats_anonymous_dataset_destination_as_no_destination():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job789", "location": "US", "projectId": "proj"},
                    "jobConfiguration": {
                        "query": {
                            "destinationTable": {
                                "projectId": "proj",
                                "datasetId": "_dc808a0dc9597042ed10aa06b088d1851477dbb9",
                                "tableId": "anon7160e641_c778_4dc8_8e1e_ec80da94a128",
                            }
                        }
                    },
                    "jobStatistics": {
                        "endTime": "2026-08-14T10:00:00Z",
                        "referencedTables": [
                            {"projectId": "proj", "datasetId": "TRUSTED", "tableId": "ga4_sessions"}
                        ],
                    },
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.destination_table is None
    assert event.referenced_tables == [("proj", "TRUSTED", "ga4_sessions")]


def test_parse_entry_returns_none_when_payload_is_not_a_dict():
    assert repository._parse_entry(_entry(None)) is None
    assert repository._parse_entry(_entry("not a dict")) is None


def test_parse_entry_returns_none_when_job_completed_event_missing():
    assert repository._parse_entry(_entry({"serviceData": {}})) is None
    assert repository._parse_entry(_entry({})) is None


def test_parse_entry_handles_missing_end_time():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job1", "location": "US", "projectId": "proj"},
                    "jobStatistics": {"referencedTables": []},
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.timestamp is None


# --- list_access_events ---------------------------------------------------------


def test_list_access_events_raises_logging_access_denied():
    client = MagicMock()
    client.list_entries.side_effect = Forbidden("denied")

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_access_events(client, "observability-hub-dev")


def test_list_access_events_raises_when_permission_denied_during_iteration():
    def _raise_on_iter():
        raise Forbidden("denied")
        yield  # pragma: no cover

    client = MagicMock()
    client.list_entries.return_value = _raise_on_iter()

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_access_events(client, "observability-hub-dev")


def test_list_access_events_parses_valid_entries_and_skips_invalid_ones():
    valid_payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job1", "location": "US", "projectId": "proj"},
                    "jobStatistics": {"endTime": "2026-08-14T10:00:00Z", "referencedTables": []},
                }
            }
        }
    }
    client = MagicMock()
    client.list_entries.return_value = [_entry(valid_payload), _entry(None)]

    events = repository.list_access_events(client, "observability-hub-dev")

    assert len(events) == 1
    assert events[0].job_id == "job1"
    client.list_entries.assert_called_once()
    call_kwargs = client.list_entries.call_args.kwargs
    assert call_kwargs["resource_names"] == ["projects/observability-hub-dev"]
    assert 'resource.type="bigquery_resource"' in call_kwargs["filter_"]
