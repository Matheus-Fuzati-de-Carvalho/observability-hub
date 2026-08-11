from datetime import UTC, datetime, timedelta
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


def test_get_table_freshness_fetches_metadata_via_get_table_and_classifies_sla():
    """last_modified_time/size_bytes/row_count agora vêm de client.get_table()
    (tempo real), não mais de TABLE_STORAGE (lag de até 24h) — o repository
    lista as tabelas via TABLES e calcula sla_status/hours_since_update em
    Python a partir de Table.modified."""
    rows = [_row(table_id="crm_leads", table_type="BASE TABLE")]
    client = _client_returning([rows])
    stale_modified = datetime.now(UTC) - timedelta(hours=800)
    client.get_table.return_value = SimpleNamespace(
        num_rows=10000, num_bytes=849813, modified=stale_modified
    )

    result = repository.get_table_freshness(client, "proj", "RAW", "US")

    assert len(result) == 1
    assert result[0]["table_id"] == "crm_leads"
    assert result[0]["table_type"] == "TABLE"
    assert result[0]["sla_status"] == "stale"
    assert result[0]["row_count"] == 10000
    assert result[0]["size_bytes"] == 849813
    client.get_table.assert_called_once_with("proj.RAW.crm_leads")


def test_get_table_freshness_query_lists_tables_not_table_storage():
    captured = {}

    def fake_query(sql, job_config=None):
        captured["sql"] = sql
        job = MagicMock()
        job.result.return_value = []
        return job

    client = MagicMock()
    client.query.side_effect = fake_query

    repository.get_table_freshness(client, "proj", "RAW", "US")

    assert "INFORMATION_SCHEMA.TABLES" in captured["sql"]
    assert "TABLE_STORAGE" not in captured["sql"]


def test_get_table_freshness_null_modified_time_yields_null_sla_status():
    """Tabela sem Table.modified (ainda não propagado) não deve cair em
    'stale' por engano — mesma proteção que _sla_status_case_sql tinha em SQL,
    agora replicada em Python por _sla_status."""
    rows = [_row(table_id="brand_new", table_type="BASE TABLE")]
    client = _client_returning([rows])
    client.get_table.return_value = SimpleNamespace(num_rows=0, num_bytes=0, modified=None)

    result = repository.get_table_freshness(client, "proj", "RAW", "US")

    assert result[0]["sla_status"] is None
    assert result[0]["hours_since_update"] is None


def test_get_table_freshness_sorts_by_hours_since_update_desc_nulls_last():
    rows = [
        _row(table_id="fresh", table_type="BASE TABLE"),
        _row(table_id="stale_table", table_type="BASE TABLE"),
        _row(table_id="no_data", table_type="BASE TABLE"),
    ]
    client = _client_returning([rows])
    now = datetime.now(UTC)
    bq_tables = {
        "proj.RAW.fresh": SimpleNamespace(num_rows=1, num_bytes=1, modified=now),
        "proj.RAW.stale_table": SimpleNamespace(
            num_rows=1, num_bytes=1, modified=now - timedelta(days=60)
        ),
        "proj.RAW.no_data": SimpleNamespace(num_rows=None, num_bytes=None, modified=None),
    }
    client.get_table.side_effect = lambda ref: bq_tables[ref]

    result = repository.get_table_freshness(client, "proj", "RAW", "US")

    assert [t["table_id"] for t in result] == ["stale_table", "fresh", "no_data"]
