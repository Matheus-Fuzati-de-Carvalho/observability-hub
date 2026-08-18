from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core.exceptions import LoggingAccessDeniedError, StorageAccessDeniedError
from observability_hub.domains.storage import repository

_PROJECT_ID = "observability-hub-dev"
_NOW = datetime(2026, 8, 17, tzinfo=UTC)


def _blob(size=0, storage_class="STANDARD", custom_time=None, updated=None):
    return SimpleNamespace(
        size=size, storage_class=storage_class, custom_time=custom_time, updated=updated
    )


def _days_ago(days):
    return _NOW - timedelta(days=days)


def _entry(payload):
    return SimpleNamespace(payload=payload)


def test_list_buckets_returns_client_result():
    client = MagicMock()
    bucket = SimpleNamespace(name="landing")
    client.list_buckets.return_value = iter([bucket])

    result = repository.list_buckets(client, _PROJECT_ID)

    assert result == [bucket]
    client.list_buckets.assert_called_once_with(project=_PROJECT_ID)


def test_list_buckets_raises_storage_access_denied_on_forbidden():
    client = MagicMock()
    client.list_buckets.side_effect = Forbidden("nope")

    with pytest.raises(StorageAccessDeniedError):
        repository.list_buckets(client, _PROJECT_ID)


def test_get_bucket_size_and_count_sums_blob_sizes(monkeypatch):
    blobs = [_blob(100), _blob(200), _blob(None)]
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: blobs)

    total_size, count = repository.get_bucket_size_and_count(MagicMock(), _PROJECT_ID, "landing")

    assert total_size == 300
    assert count == 3


def test_get_bucket_size_and_count_raises_storage_access_denied_on_forbidden(monkeypatch):
    def _raise(client, name):
        raise Forbidden("nope")

    monkeypatch.setattr(repository, "list_bucket_objects_cached", _raise)

    with pytest.raises(StorageAccessDeniedError):
        repository.get_bucket_size_and_count(MagicMock(), _PROJECT_ID, "landing")


def test_get_buckets_sizes_and_counts_runs_per_bucket(monkeypatch):
    sizes = {"landing": [_blob(10)], "processed": [_blob(20), _blob(30)]}
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: sizes[name])

    result = repository.get_buckets_sizes_and_counts(
        MagicMock(), _PROJECT_ID, ["landing", "processed"]
    )

    assert result == {"landing": (10, 1), "processed": (50, 2)}


def test_get_buckets_sizes_and_counts_empty_list_returns_empty_dict():
    assert repository.get_buckets_sizes_and_counts(MagicMock(), _PROJECT_ID, []) == {}


def test_get_eligible_waste_objects_filters_by_class_and_age(monkeypatch):
    blobs = [
        _blob(size=1, storage_class="STANDARD", updated=_days_ago(90)),  # elegível
        _blob(size=2, storage_class="NEARLINE", updated=_days_ago(90)),  # classe errada
        _blob(size=3, storage_class="STANDARD", updated=_days_ago(10)),  # recente demais
    ]
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: blobs)

    result = repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "landing", 60, _NOW)

    assert result == [blobs[0]]


def test_get_eligible_waste_objects_prefers_custom_time(monkeypatch):
    blob = _blob(size=1, storage_class="STANDARD", custom_time=_days_ago(90), updated=_days_ago(1))
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: [blob])

    result = repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "landing", 60, _NOW)

    assert result == [blob]


def test_get_eligible_waste_objects_ignores_blob_without_timestamp(monkeypatch):
    blob = _blob(size=1, storage_class="STANDARD", custom_time=None, updated=None)
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: [blob])

    result = repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "landing", 60, _NOW)

    assert result == []


def test_get_eligible_waste_objects_empty_bucket(monkeypatch):
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: [])

    assert (
        repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "archive", 60, _NOW) == []
    )


def test_get_eligible_waste_objects_raises_storage_access_denied_on_forbidden(monkeypatch):
    def _raise(client, name):
        raise Forbidden("nope")

    monkeypatch.setattr(repository, "list_bucket_objects_cached", _raise)

    with pytest.raises(StorageAccessDeniedError):
        repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "landing", 60, _NOW)


def test_parse_resource_name_extracts_bucket_and_object():
    result = repository._parse_resource_name(
        "projects/_/buckets/landing/objects/crm_leads/2026-08-17/part-0001.csv"
    )
    assert result == ("landing", "crm_leads/2026-08-17/part-0001.csv")


def test_parse_resource_name_returns_none_for_bucket_only():
    assert repository._parse_resource_name("projects/_/buckets/landing") is None


def test_parse_resource_name_returns_none_for_empty():
    assert repository._parse_resource_name(None) is None
    assert repository._parse_resource_name("") is None


def test_list_read_object_keys_parses_object_get_events():
    client = MagicMock()
    read_payload = {
        "resourceName": "projects/_/buckets/landing/objects/crm_leads/part-0001.csv",
        "methodName": "storage.objects.get",
    }
    # entrada sem resourceName (ex: evento de bucket, não de objeto) é ignorada
    other_payload = {"methodName": "storage.buckets.getStorageLayout"}
    client.list_entries.return_value = [_entry(read_payload), _entry(other_payload), _entry(None)]

    result = repository.list_read_object_keys(client, _PROJECT_ID, 90)

    assert result == {("landing", "crm_leads/part-0001.csv")}


def test_list_read_object_keys_empty_when_no_entries():
    client = MagicMock()
    client.list_entries.return_value = []

    assert repository.list_read_object_keys(client, _PROJECT_ID, 90) == set()


def test_list_read_object_keys_raises_logging_access_denied_on_forbidden():
    client = MagicMock()
    client.list_entries.side_effect = Forbidden("denied")

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_read_object_keys(client, _PROJECT_ID, 90)
