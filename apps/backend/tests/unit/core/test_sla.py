from datetime import UTC, datetime, timedelta

from observability_hub.core import sla


def test_hours_since_none_when_modified_is_none():
    assert sla.hours_since(None) is None


def test_hours_since_computes_elapsed_hours():
    modified = datetime.now(UTC) - timedelta(hours=5)
    result = sla.hours_since(modified)
    assert result is not None
    assert 4.9 < result < 5.1


def test_sla_status_none_when_hours_is_none():
    assert sla.sla_status(None) is None


def test_sla_status_thresholds():
    assert sla.sla_status(0) == "ok"
    assert sla.sla_status(12) == "ok"
    assert sla.sla_status(12.1) == "warning_12_24"
    assert sla.sla_status(24) == "warning_12_24"
    assert sla.sla_status(48) == "warning_24_48"
    assert sla.sla_status(168) == "warning_48_7d"
    assert sla.sla_status(720) == "warning_7d_1m"
    assert sla.sla_status(720.1) == "stale"
    assert sla.sla_status(10_000) == "stale"
