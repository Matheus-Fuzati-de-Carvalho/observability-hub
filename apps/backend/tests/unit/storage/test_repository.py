from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core.exceptions import StorageAccessDeniedError
from observability_hub.domains.storage import repository


def _blob(size=0, custom_time=None, updated=None):
    return SimpleNamespace(size=size, custom_time=custom_time, updated=updated)


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


def test_get_bucket_last_modified_prefers_custom_time_over_updated(monkeypatch):
    custom = datetime(2026, 8, 17, tzinfo=UTC)
    updated = datetime(2026, 8, 10, tzinfo=UTC)
    blobs = [_blob(custom_time=custom, updated=updated)]
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: blobs)

    result = repository.get_bucket_last_modified(MagicMock(), "landing")

    assert result == custom


def test_get_bucket_last_modified_falls_back_to_updated_when_no_custom_time(monkeypatch):
    updated = datetime(2026, 8, 10, tzinfo=UTC)
    blobs = [_blob(custom_time=None, updated=updated)]
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: blobs)

    result = repository.get_bucket_last_modified(MagicMock(), "landing")

    assert result == updated


def test_get_bucket_last_modified_returns_max_across_objects(monkeypatch):
    older = datetime(2026, 8, 1, tzinfo=UTC)
    newer = datetime(2026, 8, 17, tzinfo=UTC)
    blobs = [_blob(updated=older), _blob(updated=newer)]
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: blobs)

    result = repository.get_bucket_last_modified(MagicMock(), "landing")

    assert result == newer


def test_get_bucket_last_modified_returns_none_for_empty_bucket(monkeypatch):
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: [])

    assert repository.get_bucket_last_modified(MagicMock(), "archive") is None
