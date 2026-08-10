from types import SimpleNamespace
from unittest.mock import MagicMock

from observability_hub.domains.freshness import repository


def _row(**kwargs):
    return SimpleNamespace(**kwargs)


def _client_returning(rows_sequence):
    """Client cujo client.query(...).result() retorna, em sequência, cada
    lista de rows_sequence a cada chamada (uma por região/query)."""
    client = MagicMock()
    call_results = iter(rows_sequence)

    def fake_query(*args, **kwargs):
        job = MagicMock()
        job.result.return_value = next(call_results)
        return job

    client.query.side_effect = fake_query
    return client


def test_sla_status_case_sql_guards_null_timestamp_before_comparisons():
    """Sem esse guard, TIMESTAMP_DIFF(NOW, NULL, HOUR) é NULL, NULL <= 12 nunca
    é TRUE, e a lógica de três valores do SQL cairia no ELSE 'stale' para
    tabelas sem storage_last_modified_time — miscontando ausência de dado
    como o pior status possível."""
    sql = repository._sla_status_case_sql("ts.storage_last_modified_time")
    assert "WHEN ts.storage_last_modified_time IS NULL THEN NULL" in sql
    assert sql.index("IS NULL THEN NULL") < sql.index("<= 12")


def test_get_freshness_summary_by_dataset_runs_one_query_per_region():
    rows_us = [
        _row(
            dataset_id="RAW",
            location="US",
            total_tables=3,
            ok=0,
            warning_12_24=0,
            warning_24_48=0,
            warning_48_7d=0,
            warning_7d_1m=0,
            stale=3,
        )
    ]
    rows_eu: list = []
    client = _client_returning([rows_us, rows_eu])

    result = repository.get_freshness_summary_by_dataset(client, "proj", ["US", "EU"])

    assert client.query.call_count == 2
    assert len(result) == 1
    assert result[0]["dataset_id"] == "RAW"
    assert result[0]["stale"] == 3


def test_get_freshness_summary_by_dataset_query_joins_from_schemata():
    """JOIN precisa partir de SCHEMATA (não de TABLE_STORAGE) para um
    dataset vazio aparecer com total_tables=0 em vez de sumir da lista."""
    captured = {}

    def fake_query(sql, job_config=None):
        captured["sql"] = sql
        job = MagicMock()
        job.result.return_value = []
        return job

    client = MagicMock()
    client.query.side_effect = fake_query

    repository.get_freshness_summary_by_dataset(client, "proj", ["US"])

    assert "FROM `proj.region-US.INFORMATION_SCHEMA.SCHEMATA` s" in captured["sql"]
    assert "LEFT JOIN `proj.region-US.INFORMATION_SCHEMA.TABLE_STORAGE` ts" in captured["sql"]


def test_get_table_freshness_maps_raw_table_type_and_storage_columns():
    rows = [
        _row(
            table_id="crm_leads",
            table_type="BASE TABLE",
            last_modified_time="2024-01-15T00:00:00Z",
            hours_since_update=14424.0,
            size_bytes=849813,
            row_count=10000,
            sla_status="stale",
        )
    ]
    client = _client_returning([rows])

    result = repository.get_table_freshness(client, "proj", "RAW", "US")

    assert len(result) == 1
    assert result[0]["table_id"] == "crm_leads"
    assert result[0]["table_type"] == "TABLE"
    assert result[0]["sla_status"] == "stale"


def test_get_table_freshness_query_uses_storage_last_modified_time():
    """A spec original referenciava TABLE_STORAGE.last_modified_time, que não
    existe — o campo real é storage_last_modified_time."""
    captured = {}

    def fake_query(sql, job_config=None):
        captured["sql"] = sql
        job = MagicMock()
        job.result.return_value = []
        return job

    client = MagicMock()
    client.query.side_effect = fake_query

    repository.get_table_freshness(client, "proj", "RAW", "US")

    assert "storage_last_modified_time" in captured["sql"]
    assert "AS last_modified_time" in captured["sql"]
