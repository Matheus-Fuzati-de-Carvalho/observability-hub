from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden, NotFound

from observability_hub.core import bigquery as bigquery_module
from observability_hub.core.bigquery import (
    discover_regions,
    get_table_cached,
    get_tables_metadata,
    resolve_dataset_region,
)
from observability_hub.core.exceptions import (
    DatasetNotFoundError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
)

# Cache limpo entre testes por tests/conftest.py::_clear_bigquery_table_cache
# (autouse) — necessário porque o cache é keyed só por table_ref, não por
# client, e vários testes reusam os mesmos table_refs.


def _row(**kwargs):
    return SimpleNamespace(**kwargs)


def _client_returning(rows_sequence):
    """Client cujo client.query(...).result() retorna, em sequência, cada
    lista de rows_sequence a cada chamada (uma por região candidata)."""
    client = MagicMock()
    call_results = iter(rows_sequence)

    def fake_query(*args, **kwargs):
        job = MagicMock()
        job.result.return_value = next(call_results)
        return job

    client.query.side_effect = fake_query
    return client


def test_discover_regions_returns_regions_with_data():
    def probe(client, project_id, region):
        return region if region == "US" else None

    result = discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)

    assert result == ["US"]


def test_discover_regions_returns_empty_list_for_accessible_empty_project():
    def probe(client, project_id, region):
        return None

    result = discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)

    assert result == []


def test_discover_regions_raises_access_denied_when_any_region_forbidden():
    def probe(client, project_id, region):
        if region == "US":
            raise Forbidden("no access")

    with pytest.raises(ProjectAccessDeniedError):
        discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)


def test_discover_regions_raises_not_found_when_all_regions_not_found():
    def probe(client, project_id, region):
        raise NotFound("no project")

    with pytest.raises(ProjectNotFoundError):
        discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)


def test_discover_regions_prefers_found_data_over_errors_in_other_regions():
    def probe(client, project_id, region):
        if region == "US":
            return "US"
        raise NotFound("no data here")

    result = discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)

    assert result == ["US"]


def test_resolve_dataset_region_returns_first_matching_region():
    client = _client_returning([[], [_row(location="US")]])

    region = resolve_dataset_region(client, "proj", "RAW", ["EU", "US"])

    assert region == "US"
    assert client.query.call_count == 2


def test_resolve_dataset_region_raises_when_not_found_anywhere():
    client = _client_returning([[], []])

    with pytest.raises(DatasetNotFoundError):
        resolve_dataset_region(client, "proj", "GHOST", ["US", "EU"])


def test_get_table_cached_calls_get_table_once_and_reuses_cache():
    client = MagicMock()
    client.get_table.return_value = SimpleNamespace(num_rows=10)

    first = get_table_cached(client, "proj.RAW.events")
    second = get_table_cached(client, "proj.RAW.events")

    assert first is second
    client.get_table.assert_called_once_with("proj.RAW.events")


def test_get_table_cached_refetches_after_ttl_expires(monkeypatch):
    client = MagicMock()
    client.get_table.side_effect = [SimpleNamespace(num_rows=10), SimpleNamespace(num_rows=20)]
    fake_now = [1000.0]
    monkeypatch.setattr(bigquery_module.time, "monotonic", lambda: fake_now[0])

    first = get_table_cached(client, "proj.RAW.events")
    fake_now[0] += bigquery_module._TABLE_CACHE_TTL_SECONDS + 1
    second = get_table_cached(client, "proj.RAW.events")

    assert first.num_rows == 10
    assert second.num_rows == 20
    assert client.get_table.call_count == 2


def test_get_tables_metadata_returns_empty_dict_for_empty_input():
    client = MagicMock()

    result = get_tables_metadata(client, [])

    assert result == {}
    client.get_table.assert_not_called()


def test_get_tables_metadata_fetches_each_ref_and_keys_result_by_ref():
    client = MagicMock()
    tables_by_ref = {
        "proj.RAW.a": SimpleNamespace(num_rows=1),
        "proj.RAW.b": SimpleNamespace(num_rows=2),
    }
    client.get_table.side_effect = lambda ref: tables_by_ref[ref]

    result = get_tables_metadata(client, ["proj.RAW.a", "proj.RAW.b"])

    assert result["proj.RAW.a"].num_rows == 1
    assert result["proj.RAW.b"].num_rows == 2
    assert client.get_table.call_count == 2


def test_get_tables_metadata_maps_missing_table_to_none_instead_of_raising():
    client = MagicMock()

    def fake_get_table(ref):
        if ref == "proj.RAW.ghost":
            raise NotFound("dropped mid-request")
        return SimpleNamespace(num_rows=1)

    client.get_table.side_effect = fake_get_table

    result = get_tables_metadata(client, ["proj.RAW.a", "proj.RAW.ghost"])

    assert result["proj.RAW.a"].num_rows == 1
    assert result["proj.RAW.ghost"] is None
