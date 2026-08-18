from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core.exceptions import StorageAccessDeniedError
from observability_hub.domains.storage import repository


def _blob(size=0):
    return SimpleNamespace(size=size)


def test_list_buckets_returns_client_result():
    client = MagicMock()
    bucket = SimpleNamespace(name="landing")
    client.list_buckets.return_value = iter([bucket])

    result = repository.list_buckets(client, "observability-hub-dev")

    assert result == [bucket]
    client.list_buckets.assert_called_once_with(project="observability-hub-dev")


def test_list_buckets_raises_storage_access_denied_on_forbidden():
    client = MagicMock()
    client.list_buckets.side_effect = Forbidden("nope")

    with pytest.raises(StorageAccessDeniedError):
        repository.list_buckets(client, "observability-hub-dev")


def test_get_bucket_size_and_count_sums_blob_sizes(monkeypatch):
    blobs = [_blob(100), _blob(200), _blob(None)]
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: blobs)

    total_size, count = repository.get_bucket_size_and_count(MagicMock(), "landing")

    assert total_size == 300
    assert count == 3


def test_get_buckets_sizes_and_counts_runs_per_bucket(monkeypatch):
    sizes = {"landing": [_blob(10)], "processed": [_blob(20), _blob(30)]}
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: sizes[name])

    result = repository.get_buckets_sizes_and_counts(MagicMock(), ["landing", "processed"])

    assert result == {"landing": (10, 1), "processed": (50, 2)}


def test_get_buckets_sizes_and_counts_empty_list_returns_empty_dict():
    assert repository.get_buckets_sizes_and_counts(MagicMock(), []) == {}
