from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from observability_hub.domains.storage import service
from observability_hub.domains.storage.schemas import BucketSummary, MinDaysUnused

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
        lambda client, project_id, names: {"landing": (1000, 1), "processed": (500, 1)},
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
        service.repository, "get_buckets_sizes_and_counts", lambda client, project_id, names: {}
    )

    result = service.list_buckets(MagicMock(), "observability-hub-dev")

    assert result.buckets == []


def _blob(size):
    return SimpleNamespace(size=size, custom_time=None, updated=_UPDATED)


def test_get_waste_candidates_skips_buckets_with_lifecycle_rule(monkeypatch):
    buckets = [_bucket("landing", lifecycle_rules=[{"action": {"type": "SetStorageClass"}}])]
    monkeypatch.setattr(service.repository, "list_buckets", lambda client, project_id: buckets)
    called = MagicMock()
    monkeypatch.setattr(service.repository, "get_eligible_waste_objects", called)

    result = service.get_waste_candidates(MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY)

    assert result.candidates == []
    called.assert_not_called()


def test_get_waste_candidates_skips_bucket_without_eligible_objects(monkeypatch):
    buckets = [_bucket("processed", lifecycle_rules=[])]
    monkeypatch.setattr(service.repository, "list_buckets", lambda client, project_id: buckets)
    monkeypatch.setattr(
        service.repository,
        "get_eligible_waste_objects",
        lambda client, project_id, name, days, now: [],
    )

    result = service.get_waste_candidates(MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY)

    assert result.candidates == []


def test_get_waste_candidates_computes_savings_range(monkeypatch):
    buckets = [_bucket("processed", lifecycle_rules=[])]
    one_gib = 1024**3
    eligible = [_blob(one_gib)]
    monkeypatch.setattr(service.repository, "list_buckets", lambda client, project_id: buckets)
    monkeypatch.setattr(
        service.repository,
        "get_eligible_waste_objects",
        lambda client, project_id, name, days, now: eligible,
    )

    result = service.get_waste_candidates(MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY)

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.bucket_name == "processed"
    assert candidate.eligible_object_count == 1
    assert candidate.eligible_size_bytes == one_gib
    # 1 GiB * (0.020 - 0.010) = 0.010 ; 1 GiB * (0.020 - 0.004) = 0.016
    assert candidate.estimated_savings_usd_month_min == 0.01
    assert candidate.estimated_savings_usd_month_max == 0.016
    assert result.min_days_unused == MinDaysUnused.SIXTY
    assert result.savings_disclaimer
    assert result.limitation
