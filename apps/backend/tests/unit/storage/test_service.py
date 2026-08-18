from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from observability_hub.domains.storage import service
from observability_hub.domains.storage.schemas import BucketSummary

_CREATED = datetime(2026, 1, 1, tzinfo=UTC)
_UPDATED = datetime(2026, 8, 17, tzinfo=UTC)


def _bucket(
    name,
    location="US",
    storage_class="STANDARD",
    lifecycle_rules=(),
    time_created=_CREATED,
    updated=_UPDATED,
):
    return SimpleNamespace(
        name=name,
        location=location,
        storage_class=storage_class,
        lifecycle_rules=lifecycle_rules,
        time_created=time_created,
        updated=updated,
    )


def test_list_buckets_builds_response(monkeypatch):
    buckets = [
        _bucket("landing", lifecycle_rules=[{"action": {"type": "SetStorageClass"}}]),
        _bucket("processed", storage_class="NEARLINE", lifecycle_rules=[]),
    ]
    monkeypatch.setattr(service.repository, "list_buckets", lambda client, project_id: buckets)
    monkeypatch.setattr(
        service.repository,
        "get_buckets_sizes_and_counts",
        lambda client, names: {"landing": (1000, 1), "processed": (500, 1)},
    )

    result = service.list_buckets(MagicMock(), "observability-hub-dev")

    assert result.buckets == [
        BucketSummary(
            name="landing",
            location="US",
            storage_class="STANDARD",
            total_size_bytes=1000,
            object_count=1,
            has_lifecycle_rule=True,
            time_created=_CREATED,
            updated=_UPDATED,
        ),
        BucketSummary(
            name="processed",
            location="US",
            storage_class="NEARLINE",
            total_size_bytes=500,
            object_count=1,
            has_lifecycle_rule=False,
            time_created=_CREATED,
            updated=_UPDATED,
        ),
    ]


def test_list_buckets_empty_project(monkeypatch):
    monkeypatch.setattr(service.repository, "list_buckets", lambda client, project_id: [])
    monkeypatch.setattr(
        service.repository, "get_buckets_sizes_and_counts", lambda client, names: {}
    )

    result = service.list_buckets(MagicMock(), "observability-hub-dev")

    assert result.buckets == []
