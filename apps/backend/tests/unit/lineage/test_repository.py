from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core.exceptions import LoggingAccessDeniedError
from observability_hub.domains.lineage import repository


def _entry(payload: dict | None):
    return SimpleNamespace(payload=payload)


# Payload real, capturado via `gcloud logging read --format=json` em
# observability-hub-dev (2026-08-14) para o CTAS de
# `TRUSTED.ga4_sessions AS SELECT ... FROM RAW.ga4_events`. É o campo
# `protoPayload` do log entry, formato legado `AuditData`/
# `jobCompletedEvent` — não o `BigQueryAuditMetadata`/`jobChange` da doc
# de migração (ver docstring de repository.py).
REAL_CTAS_PROTO_PAYLOAD = {
    "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
    "authenticationInfo": {
        "oauthInfo": {"oauthClientId": "32555940559.apps.googleusercontent.com"},
        "principalEmail": "fuzatimatheus.cloud@gmail.com",
    },
    "methodName": "jobservice.jobcompleted",
    "requestMetadata": {
        "callerIp": "200.205.43.10",
        "callerSuppliedUserAgent": "google-cloud-sdk578.0.0 google-api-python-client command/bq.query.jobs",
        "destinationAttributes": {},
        "requestAttributes": {},
    },
    "resourceName": "projects/observability-hub-dev/jobs/bqjob_r5bf5dfa96120dc26_000001a000b0cfae_1",
    "serviceData": {
        "@type": "type.googleapis.com/google.cloud.bigquery.logging.v1.AuditData",
        "jobCompletedEvent": {
            "eventName": "query_job_completed",
            "job": {
                "jobConfiguration": {
                    "query": {
                        "createDisposition": "CREATE_IF_NEEDED",
                        "defaultDataset": {},
                        "destinationTable": {
                            "datasetId": "TRUSTED",
                            "projectId": "observability-hub-dev",
                            "tableId": "ga4_sessions",
                        },
                        "query": (
                            "CREATE OR REPLACE TABLE `observability-hub-dev.TRUSTED.ga4_sessions` AS "
                            "SELECT event_date, user_pseudo_id, COUNT(*) AS total_events, "
                            "SUM(CASE WHEN event_name = 'purchase' THEN revenue ELSE 0 END) AS revenue "
                            "FROM `observability-hub-dev.RAW.ga4_events` GROUP BY 1, 2;"
                        ),
                        "queryPriority": "QUERY_INTERACTIVE",
                        "statementType": "CREATE_TABLE_AS_SELECT",
                        "writeDisposition": "WRITE_EMPTY",
                    }
                },
                "jobName": {
                    "jobId": "bqjob_r5bf5dfa96120dc26_000001a000b0cfae_1",
                    "location": "US",
                    "projectId": "observability-hub-dev",
                },
                "jobStatistics": {
                    "billingTier": 1,
                    "createTime": "2026-08-14T14:33:03.171Z",
                    "endTime": "2026-08-14T14:33:05.199Z",
                    "queryOutputRowCount": "9964",
                    "referencedTables": [
                        {
                            "datasetId": "RAW",
                            "projectId": "observability-hub-dev",
                            "tableId": "ga4_events",
                        }
                    ],
                    "reservation": "unreserved",
                    "startTime": "2026-08-14T14:33:03.625Z",
                    "totalBilledBytes": "10485760",
                    "totalProcessedBytes": "4352799",
                    "totalSlotMs": "1426",
                    "totalTablesProcessed": 1,
                },
                "jobStatus": {"error": {}, "state": "DONE"},
            },
        },
    },
    "serviceName": "bigquery.googleapis.com",
    "status": {},
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


# --- _parse_entry -------------------------------------------------------------


def test_parse_entry_extracts_referenced_and_destination_tables_from_real_payload():
    event = repository._parse_entry(_entry(REAL_CTAS_PROTO_PAYLOAD))

    assert event is not None
    assert event.job_id == "bqjob_r5bf5dfa96120dc26_000001a000b0cfae_1"
    assert event.principal_email == "fuzatimatheus.cloud@gmail.com"
    assert event.destination_table == ("observability-hub-dev", "TRUSTED", "ga4_sessions")
    assert event.referenced_tables == [("observability-hub-dev", "RAW", "ga4_events")]


def test_parse_entry_falls_back_to_load_config_destination():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job456", "location": "US", "projectId": "proj"},
                    "jobConfiguration": {
                        "load": {
                            "destinationTable": {
                                "projectId": "proj",
                                "datasetId": "RAW",
                                "tableId": "crm_leads",
                            }
                        }
                    },
                    "jobStatistics": {},
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.destination_table == ("proj", "RAW", "crm_leads")
    assert event.referenced_tables == []


def test_parse_entry_treats_anonymous_dataset_destination_as_no_destination():
    """SELECT interativo sem destino explícito ganha uma destinationTable
    de cache num dataset anônimo do BigQuery (prefixo "_") — não é
    lineage real, não deve aparecer como downstream."""
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
                        "referencedTables": [
                            {"projectId": "proj", "datasetId": "TRUSTED", "tableId": "ga4_sessions"}
                        ]
                    },
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.destination_table is None
    assert event.referenced_tables == [("proj", "TRUSTED", "ga4_sessions")]


# Payloads reais capturados ao vivo em observability-hub-dev
# (2026-08-17/18, ver docs/specs/storage.md seção 7.1) — jobConfiguration
# de LOAD (GCS -> BQ) e EXTRACT (BQ -> GCS), chaves irmãs de "query".
REAL_LOAD_JOB_CONFIG = {
    "load": {
        "sourceUris": ["gs://observability-hub-dev-landing/crm_leads/2026-08-17/part-0001.csv"],
        "destinationTable": {
            "projectId": "observability-hub-dev",
            "datasetId": "RAW",
            "tableId": "crm_leads_staging",
        },
        "createDisposition": "CREATE_IF_NEEDED",
        "writeDisposition": "WRITE_APPEND",
    }
}

REAL_EXTRACT_JOB_CONFIG = {
    "extract": {
        "destinationUris": ["gs://observability-hub-dev-processed/exports/crm_leads_staging.csv"],
        "sourceTable": {
            "projectId": "observability-hub-dev",
            "datasetId": "RAW",
            "tableId": "crm_leads_staging",
        },
    }
}


def test_parse_bucket_name_extracts_first_segment():
    assert repository._parse_bucket_name("gs://landing/crm_leads/part-0001.csv") == "landing"


def test_parse_bucket_name_handles_wildcard_path():
    """Seção 7.3 da spec: wildcard não testado ao vivo, mas a lógica não
    depende do resto do path ser literal — só o primeiro segmento importa."""
    assert repository._parse_bucket_name("gs://landing/crm_leads/*.csv") == "landing"


@pytest.mark.parametrize("uri", [None, "", "https://not-gs-scheme/bucket/obj", "gs://"])
def test_parse_bucket_name_returns_none_for_invalid_input(uri):
    assert repository._parse_bucket_name(uri) is None


def test_parse_bucket_names_dedupes_and_sorts():
    uris = ["gs://b/x.csv", "gs://a/y.csv", "gs://b/z.csv"]
    assert repository._parse_bucket_names(uris) == ["a", "b"]


def test_parse_bucket_names_empty_for_none_or_empty_list():
    assert repository._parse_bucket_names(None) == []
    assert repository._parse_bucket_names([]) == []


def test_parse_entry_extracts_source_bucket_from_real_load_payload():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "load-job-1", "location": "US", "projectId": "proj"},
                    "jobConfiguration": REAL_LOAD_JOB_CONFIG,
                    "jobStatistics": {},
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.destination_table == ("observability-hub-dev", "RAW", "crm_leads_staging")
    assert event.source_buckets == ["observability-hub-dev-landing"]
    assert event.destination_buckets == []


def test_parse_entry_extracts_destination_bucket_and_source_table_from_real_extract_payload():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "extract-job-1", "location": "US", "projectId": "proj"},
                    "jobConfiguration": REAL_EXTRACT_JOB_CONFIG,
                    "jobStatistics": {},
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.destination_table is None
    assert event.referenced_tables == [("observability-hub-dev", "RAW", "crm_leads_staging")]
    assert event.destination_buckets == ["observability-hub-dev-processed"]
    assert event.source_buckets == []


def test_parse_entry_does_not_duplicate_extract_source_already_in_referenced_tables():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "extract-job-2", "location": "US", "projectId": "proj"},
                    "jobConfiguration": REAL_EXTRACT_JOB_CONFIG,
                    "jobStatistics": {
                        "referencedTables": [
                            {
                                "projectId": "observability-hub-dev",
                                "datasetId": "RAW",
                                "tableId": "crm_leads_staging",
                            }
                        ]
                    },
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.referenced_tables == [("observability-hub-dev", "RAW", "crm_leads_staging")]


def test_parse_entry_returns_none_when_payload_is_not_a_dict():
    assert repository._parse_entry(_entry(None)) is None
    assert repository._parse_entry(_entry("not a dict")) is None


def test_parse_entry_returns_none_when_job_completed_event_missing():
    assert repository._parse_entry(_entry({"serviceData": {}})) is None
    assert repository._parse_entry(_entry({})) is None


def test_parse_entry_skips_malformed_referenced_table_entries():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {},
                    "jobStatistics": {
                        "referencedTables": [
                            {"projectId": "proj", "datasetId": "RAW", "tableId": "crm_leads"},
                            {"projectId": "proj", "datasetId": "RAW"},
                        ]
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
    client.list_entries.side_effect = Forbidden("denied")

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_job_events(client, "observability-hub-dev")


def test_list_job_events_raises_when_permission_denied_during_iteration():
    """Forbidden costuma só estourar ao iterar (list_entries devolve
    um iterador preguiçoso) — não só na chamada inicial. É a exceção real
    do transporte REST (_use_grpc=False, ver core/logging_client.py) para
    um 403 — não PermissionDenied, que é a classe usada para o código gRPC
    equivalente; confirmado no log de erro real de observability-hub-dev
    ao consultar lineage de um projeto sem roles/logging.viewer."""

    def _raise_on_iter():
        raise Forbidden("denied")
        yield  # pragma: no cover

    client = MagicMock()
    client.list_entries.return_value = _raise_on_iter()

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_job_events(client, "observability-hub-dev")


def test_list_job_events_parses_valid_entries_and_skips_invalid_ones():
    valid_payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job1", "location": "US", "projectId": "proj"},
                    "jobStatistics": {"referencedTables": []},
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
