from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from observability_hub.core.exceptions import LoggingAccessDeniedError
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


def _blob(size, name="obj.csv"):
    return SimpleNamespace(size=size, name=name, custom_time=None, updated=_UPDATED)


def _mock_waste_deps(monkeypatch, buckets, eligible_by_bucket, read_keys=None, forbidden=False):
    monkeypatch.setattr(service.repository, "list_buckets", lambda client, project_id: buckets)
    monkeypatch.setattr(
        service.repository,
        "get_eligible_waste_objects",
        lambda client, project_id, name, days, now: eligible_by_bucket.get(name, []),
    )

    def _read_keys(logging_client, project_id, lookback_days):
        if forbidden:
            raise LoggingAccessDeniedError(project_id)
        return read_keys or set()

    monkeypatch.setattr(service.repository, "list_read_object_keys", _read_keys)


def test_get_waste_candidates_skips_buckets_with_lifecycle_rule(monkeypatch):
    buckets = [_bucket("landing", lifecycle_rules=[{"action": {"type": "SetStorageClass"}}])]
    _mock_waste_deps(monkeypatch, buckets, {}, read_keys={("landing", "obj.csv")})
    called = MagicMock()
    monkeypatch.setattr(service.repository, "get_eligible_waste_objects", called)

    result = service.get_waste_candidates(
        MagicMock(), MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY
    )

    assert result.candidates == []
    called.assert_not_called()


def test_get_waste_candidates_skips_bucket_without_eligible_objects(monkeypatch):
    buckets = [_bucket("processed", lifecycle_rules=[])]
    _mock_waste_deps(monkeypatch, buckets, {}, read_keys={("processed", "obj.csv")})

    result = service.get_waste_candidates(
        MagicMock(), MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY
    )

    assert result.candidates == []


def test_get_waste_candidates_computes_savings_range(monkeypatch):
    buckets = [_bucket("processed", lifecycle_rules=[])]
    one_gib = 1024**3
    eligible = [_blob(one_gib)]
    _mock_waste_deps(
        monkeypatch, buckets, {"processed": eligible}, read_keys={("processed", "obj.csv")}
    )

    result = service.get_waste_candidates(
        MagicMock(), MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY
    )

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


def test_get_waste_candidates_usage_confirmed_when_all_unread(monkeypatch):
    buckets = [_bucket("processed", lifecycle_rules=[])]
    eligible = [_blob(100, name="a.csv"), _blob(200, name="b.csv")]
    # nenhuma das duas chaves aparece nos "lidos" -> tudo sem leitura confirmada
    _mock_waste_deps(
        monkeypatch, buckets, {"processed": eligible}, read_keys={("other-bucket", "x.csv")}
    )

    result = service.get_waste_candidates(
        MagicMock(), MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY
    )

    candidate = result.candidates[0]
    assert candidate.confidence == "usage_confirmed"
    assert candidate.usage_confirmed_object_count == 2
    assert candidate.usage_confirmed_size_bytes == 300
    assert result.usage_check_warning is None


def test_get_waste_candidates_config_based_when_partially_read(monkeypatch):
    buckets = [_bucket("processed", lifecycle_rules=[])]
    eligible = [_blob(100, name="a.csv"), _blob(200, name="b.csv")]
    # "a.csv" foi lido, "b.csv" não -> bucket fica config_based (não é 100% confirmado)
    _mock_waste_deps(
        monkeypatch, buckets, {"processed": eligible}, read_keys={("processed", "a.csv")}
    )

    result = service.get_waste_candidates(
        MagicMock(), MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY
    )

    candidate = result.candidates[0]
    assert candidate.confidence == "config_based"
    assert candidate.usage_confirmed_object_count == 1
    assert candidate.usage_confirmed_size_bytes == 200
    assert result.usage_check_warning is None


def test_get_waste_candidates_degrades_gracefully_on_forbidden(monkeypatch):
    buckets = [_bucket("processed", lifecycle_rules=[])]
    eligible = [_blob(100, name="a.csv")]
    _mock_waste_deps(monkeypatch, buckets, {"processed": eligible}, forbidden=True)

    result = service.get_waste_candidates(
        MagicMock(), MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY
    )

    candidate = result.candidates[0]
    assert candidate.confidence == "config_based"
    assert candidate.usage_confirmed_object_count == 0
    assert candidate.usage_confirmed_size_bytes == 0
    assert result.usage_check_warning is not None


def test_get_waste_candidates_degrades_gracefully_on_empty_read_keys(monkeypatch):
    buckets = [_bucket("processed", lifecycle_rules=[])]
    eligible = [_blob(100, name="a.csv")]
    _mock_waste_deps(monkeypatch, buckets, {"processed": eligible}, read_keys=set())

    result = service.get_waste_candidates(
        MagicMock(), MagicMock(), "observability-hub-dev", MinDaysUnused.SIXTY
    )

    candidate = result.candidates[0]
    assert candidate.confidence == "config_based"
    assert candidate.usage_confirmed_object_count == 0
    assert result.usage_check_warning is not None
    assert "90" in result.usage_check_warning
