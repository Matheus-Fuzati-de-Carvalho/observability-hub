from unittest.mock import MagicMock

from observability_hub.domains.quality import firestore_repository


def _fake_client_with_document(document: MagicMock) -> MagicMock:
    client = MagicMock(name="firestore.Client")
    client.collection.return_value.document.return_value = document
    return client


def test_get_last_profiling_result_returns_none_when_doc_missing():
    document = MagicMock()
    document.get.return_value.exists = False
    client = _fake_client_with_document(document)

    result = firestore_repository.get_last_profiling_result(
        client, "observability-hub-dev", "RAW", "crm_leads"
    )

    assert result is None
    client.collection.assert_called_once_with("profiling_results")
    client.collection.return_value.document.assert_called_once_with(
        "observability-hub-dev_RAW_crm_leads"
    )


def test_get_last_profiling_result_returns_dict_when_doc_exists():
    document = MagicMock()
    document.get.return_value.exists = True
    document.get.return_value.to_dict.return_value = {
        "overall_density": 87.5,
        "estimated_duplicate_pct": 2.0,
    }
    client = _fake_client_with_document(document)

    result = firestore_repository.get_last_profiling_result(
        client, "observability-hub-dev", "RAW", "crm_leads"
    )

    assert result == {"overall_density": 87.5, "estimated_duplicate_pct": 2.0}


def test_save_profiling_result_writes_expected_doc():
    document = MagicMock()
    client = _fake_client_with_document(document)

    firestore_repository.save_profiling_result(
        client,
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        overall_density=91.3,
        estimated_duplicate_pct=1.5,
        executed_by="a@dp6.com.br",
    )

    client.collection.assert_called_once_with("profiling_results")
    client.collection.return_value.document.assert_called_once_with(
        "observability-hub-dev_RAW_crm_leads"
    )
    document.set.assert_called_once()
    payload = document.set.call_args[0][0]
    assert payload["overall_density"] == 91.3
    assert payload["estimated_duplicate_pct"] == 1.5
    assert payload["executed_by"] == "a@dp6.com.br"
    assert "executed_at" in payload
