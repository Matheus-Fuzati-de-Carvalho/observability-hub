from datetime import UTC, datetime
from unittest.mock import MagicMock

from google.cloud import firestore

from observability_hub.domains.pii import history_repository


def _fake_client_with_scans_collection():
    client = MagicMock()
    pii_scan_history = MagicMock()
    table_doc = MagicMock()
    scans = MagicMock()

    client.collection.return_value = pii_scan_history
    pii_scan_history.document.return_value = table_doc
    table_doc.collection.return_value = scans

    return client, scans


def test_table_doc_id_is_deterministic():
    assert history_repository._table_doc_id("proj", "RAW", "clientes") == "proj_RAW_clientes"


def test_save_scan_writes_to_scans_subcollection_not_runs():
    client, scans = _fake_client_with_scans_collection()
    trimmed_query = MagicMock()
    scans.order_by.return_value = trimmed_query
    trimmed_query.offset.return_value = trimmed_query
    trimmed_query.stream.return_value = []

    history_repository.save_scan(
        client,
        "observability-hub-dev",
        "RAW",
        "clientes",
        executed_by="a@dp6.com.br",
        flagged_columns_count=2,
        columns=[{"column_name": "email", "flagged": True, "confidence": "high"}],
    )

    client.collection.assert_called_once_with("pii_scan_history")
    client.collection.return_value.document.assert_called_once_with(
        "observability-hub-dev_RAW_clientes"
    )
    # nome da subcoleção precisa ser "scans", não "runs" — evita colidir
    # com o collection_group("runs") do profiling.
    client.collection.return_value.document.return_value.collection.assert_called_once_with("scans")

    scans.add.assert_called_once()
    added = scans.add.call_args[0][0]
    assert added["project_id"] == "observability-hub-dev"
    assert added["dataset_id"] == "RAW"
    assert added["table_id"] == "clientes"
    assert added["executed_by"] == "a@dp6.com.br"
    assert added["flagged_columns_count"] == 2
    assert added["columns"] == [{"column_name": "email", "flagged": True, "confidence": "high"}]
    assert isinstance(added["executed_at"], datetime)
    assert added["executed_at"].tzinfo is UTC

    scans.order_by.assert_called_once_with("executed_at", direction=firestore.Query.DESCENDING)
    trimmed_query.offset.assert_called_once_with(30)


def test_save_scan_trims_overflow_docs():
    client, scans = _fake_client_with_scans_collection()
    trimmed_query = MagicMock()
    scans.order_by.return_value = trimmed_query
    trimmed_query.offset.return_value = trimmed_query
    overflow_doc = MagicMock()
    trimmed_query.stream.return_value = [overflow_doc]

    history_repository.save_scan(
        client,
        "proj",
        "RAW",
        "clientes",
        executed_by="a@dp6.com.br",
        flagged_columns_count=0,
        columns=[],
    )

    overflow_doc.reference.delete.assert_called_once()
