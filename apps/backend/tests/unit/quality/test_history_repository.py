from datetime import UTC, datetime
from unittest.mock import MagicMock

from google.cloud import firestore

from observability_hub.domains.quality import history_repository


def _fake_client_with_runs_collection():
    """MagicMock cujo client.collection("profiling_history").document(doc_id)
    .collection("runs") devolve um mock único e previsível — mesmo padrão de
    tests/unit/history/test_repository.py."""
    client = MagicMock()
    profiling_history = MagicMock()
    table_doc = MagicMock()
    runs = MagicMock()

    client.collection.return_value = profiling_history
    profiling_history.document.return_value = table_doc
    table_doc.collection.return_value = runs

    return client, runs


def test_save_run_writes_then_trims():
    client, runs = _fake_client_with_runs_collection()
    trimmed_query = MagicMock()
    runs.order_by.return_value = trimmed_query
    trimmed_query.offset.return_value = trimmed_query
    trimmed_query.stream.return_value = []

    history_repository.save_run(
        client,
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        overall_density=91.3,
        estimated_duplicate_pct=1.5,
        executed_by="a@dp6.com.br",
        columns=[{"column_name": "email", "completeness_pct": 91.3, "quality_flag": "ok"}],
    )

    client.collection.assert_called_once_with("profiling_history")
    client.collection.return_value.document.assert_called_once_with(
        "observability-hub-dev_RAW_crm_leads"
    )
    runs.add.assert_called_once()
    added = runs.add.call_args[0][0]
    assert added["project_id"] == "observability-hub-dev"
    assert added["dataset_id"] == "RAW"
    assert added["table_id"] == "crm_leads"
    assert added["overall_density"] == 91.3
    assert added["estimated_duplicate_pct"] == 1.5
    assert added["executed_by"] == "a@dp6.com.br"
    assert added["columns"] == [
        {"column_name": "email", "completeness_pct": 91.3, "quality_flag": "ok"}
    ]
    assert isinstance(added["executed_at"], datetime)
    assert added["executed_at"].tzinfo is UTC

    runs.order_by.assert_called_once_with("executed_at", direction=firestore.Query.DESCENDING)
    trimmed_query.offset.assert_called_once_with(30)


def test_trim_to_max_deletes_only_overflow_docs():
    client, runs = _fake_client_with_runs_collection()
    trimmed_query = MagicMock()
    runs.order_by.return_value = trimmed_query
    trimmed_query.offset.return_value = trimmed_query
    overflow_doc = MagicMock()
    trimmed_query.stream.return_value = [overflow_doc]

    history_repository.save_run(
        client,
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        overall_density=100.0,
        estimated_duplicate_pct=0.0,
        executed_by="a@dp6.com.br",
        columns=[],
    )

    overflow_doc.reference.delete.assert_called_once()


def test_list_runs_returns_most_recent_first():
    client, runs = _fake_client_with_runs_collection()
    ordered_query = MagicMock()
    limited_query = MagicMock()
    runs.order_by.return_value = ordered_query
    ordered_query.limit.return_value = limited_query

    doc_a = MagicMock()
    doc_a.to_dict.return_value = {"overall_density": 90.0}
    doc_b = MagicMock()
    doc_b.to_dict.return_value = {"overall_density": 80.0}
    limited_query.stream.return_value = [doc_a, doc_b]

    result = history_repository.list_runs(client, "observability-hub-dev", "RAW", "crm_leads")

    assert result == [{"overall_density": 90.0}, {"overall_density": 80.0}]
    runs.order_by.assert_called_once_with("executed_at", direction=firestore.Query.DESCENDING)
    ordered_query.limit.assert_called_once_with(30)
