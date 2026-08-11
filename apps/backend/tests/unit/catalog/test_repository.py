from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound

from observability_hub.core.exceptions import TableNotFoundError
from observability_hub.domains.catalog import repository


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


def test_bytes_to_gb():
    assert repository._bytes_to_gb(None) is None
    assert repository._bytes_to_gb(0) == 0.0
    assert repository._bytes_to_gb(2_075_443) == 0.0021


def test_get_datasets_summary_runs_one_query_per_region_and_computes_gb():
    rows_us = [
        _row(
            dataset_id="RAW",
            location="US",
            creation_time="2026-06-03T19:40:00Z",
            last_modified_time="2026-06-08T18:38:00Z",
            total_tables=3,
            total_views=0,
            total_size_bytes=2_075_443,
            total_rows=30000,
        )
    ]
    rows_eu: list = []
    client = _client_returning([rows_us, rows_eu])

    result = repository.get_datasets_summary(client, "proj", ["US", "EU"])

    assert client.query.call_count == 2
    assert len(result) == 1
    assert result[0]["dataset_id"] == "RAW"
    assert result[0]["total_size_gb"] == 0.0021


def test_resolve_dataset_region_is_reexported_from_core_bigquery():
    """Cobertura de comportamento mora em tests/unit/core/test_bigquery.py —
    aqui só garantimos que repository.resolve_dataset_region (usado por
    service.py) continua sendo o mesmo objeto de core.bigquery."""
    from observability_hub.core.bigquery import resolve_dataset_region

    assert repository.resolve_dataset_region is resolve_dataset_region


def test_row_to_table_dict_derives_partitioned_and_clustered():
    row = _row(
        table_name="events",
        table_type="BASE TABLE",
        creation_time="2026-06-08T18:38:40Z",
        column_count=8,
        partition_column="_PARTITIONTIME",
        clustering_columns=["event_name", "user_id"],
    )
    bq_table = SimpleNamespace(num_rows=10000, num_bytes=576920, modified="2026-06-08T18:38:40Z")

    result = repository._row_to_table_dict(row, "US", bq_table)

    assert result["table_id"] == "events"
    assert result["table_type"] == "TABLE"
    assert result["is_partitioned"] is True
    assert result["is_clustered"] is True
    assert result["clustering_columns"] == ["event_name", "user_id"]
    assert result["size_gb"] == round(576920 / 1_000_000_000, 4)
    assert result["row_count"] == 10000


def test_row_to_table_dict_handles_unpartitioned_unclustered_table():
    row = _row(
        table_name="events_view",
        table_type="VIEW",
        creation_time="2026-06-08T18:38:40Z",
        column_count=5,
        partition_column=None,
        clustering_columns=[],
    )
    bq_table = SimpleNamespace(num_rows=None, num_bytes=None, modified="2026-06-08T18:38:40Z")

    result = repository._row_to_table_dict(row, "US", bq_table)

    assert result["table_type"] == "VIEW"
    assert result["is_partitioned"] is False
    assert result["is_clustered"] is False
    assert result["size_gb"] is None


def test_row_to_table_dict_handles_missing_metadata():
    """bq_table é None quando a tabela sumiu entre a query de listagem e a
    chamada de client.get_table() (race) — não deve levantar exceção."""
    row = _row(
        table_name="ghost",
        table_type="BASE TABLE",
        creation_time="2026-06-08T18:38:40Z",
        column_count=1,
        partition_column=None,
        clustering_columns=[],
    )

    result = repository._row_to_table_dict(row, "US", None)

    assert result["row_count"] is None
    assert result["size_bytes"] is None
    assert result["last_modified_time"] is None


def test_get_table_columns_maps_is_nullable_yes_no():
    rows = [
        _row(column_name="id", data_type="STRING", is_nullable="NO", description=None),
        _row(column_name="email", data_type="STRING", is_nullable="YES", description="contato"),
    ]
    client = _client_returning([rows])

    result = repository.get_table_columns(client, "proj", "RAW", "leads", "US")

    assert result[0]["is_nullable"] is False
    assert result[1]["is_nullable"] is True
    assert result[1]["description"] == "contato"


def test_get_tables_summary_maps_api_table_type_to_raw_value():
    captured = {}

    def fake_query(sql, job_config=None):
        captured["sql"] = sql
        captured["params"] = job_config.query_parameters if job_config else []
        job = MagicMock()
        job.result.return_value = []
        return job

    client = MagicMock()
    client.query.side_effect = fake_query

    repository.get_tables_summary(client, "proj", "RAW", "US", table_type="MATERIALIZED_VIEW")

    assert "t.table_type = @table_type" in captured["sql"]
    param_values = {p.name: p.value for p in captured["params"]}
    assert param_values["table_type"] == "MATERIALIZED VIEW"


@pytest.mark.parametrize("location", ["US", "EU", "us-central1"])
def test_get_tables_summary_derives_partition_column_from_columns_schema(location):
    """TABLE_PARTITIONS não tem o nome da coluna de particionamento e não
    existe em US/EU — partition_column vem de COLUMNS.is_partitioning_column,
    que funciona igual em qualquer região."""
    captured = {}

    def fake_query(sql, job_config=None):
        captured["sql"] = sql
        job = MagicMock()
        job.result.return_value = []
        return job

    client = MagicMock()
    client.query.side_effect = fake_query

    repository.get_tables_summary(client, "proj", "RAW", location)

    assert "TABLE_PARTITIONS" not in captured["sql"]
    assert "is_partitioning_column" in captured["sql"]
    assert "partition_column" in captured["sql"]


def test_get_tables_summary_row_to_dict_reads_partition_column_from_columns_agg():
    rows = [
        _row(
            table_name="ga4_events",
            table_type="BASE TABLE",
            creation_time="2026-06-08T18:38:40Z",
            column_count=8,
            partition_column="event_date",
            clustering_columns=["event_name"],
        )
    ]
    client = _client_returning([rows])
    client.get_table.return_value = SimpleNamespace(
        num_rows=10000, num_bytes=576920, modified="2026-06-08T18:38:40Z"
    )

    result = repository.get_tables_summary(client, "proj", "RAW", "US")

    assert result[0]["partition_column"] == "event_date"
    assert result[0]["is_partitioned"] is True
    assert result[0]["row_count"] == 10000
    client.get_table.assert_called_once_with("proj.RAW.ga4_events")


def test_get_tables_summary_fetches_metadata_via_get_table_and_sorts_by_size_desc():
    rows = [
        _row(
            table_name="small",
            table_type="BASE TABLE",
            creation_time="2026-06-08T18:38:40Z",
            column_count=1,
            partition_column=None,
            clustering_columns=[],
        ),
        _row(
            table_name="big",
            table_type="BASE TABLE",
            creation_time="2026-06-08T18:38:40Z",
            column_count=1,
            partition_column=None,
            clustering_columns=[],
        ),
        _row(
            table_name="no_metadata",
            table_type="VIEW",
            creation_time="2026-06-08T18:38:40Z",
            column_count=1,
            partition_column=None,
            clustering_columns=[],
        ),
    ]
    client = _client_returning([rows])
    bq_tables = {
        "proj.RAW.small": SimpleNamespace(num_rows=1, num_bytes=100, modified=None),
        "proj.RAW.big": SimpleNamespace(num_rows=2, num_bytes=9000, modified=None),
    }

    def fake_get_table(ref):
        if ref not in bq_tables:
            raise NotFound(ref)
        return bq_tables[ref]

    client.get_table.side_effect = fake_get_table

    result = repository.get_tables_summary(client, "proj", "RAW", "US")

    assert [t["table_id"] for t in result] == ["big", "small", "no_metadata"]
    assert result[2]["size_bytes"] is None


def test_get_table_detail_combines_summary_columns_and_bq_table_metadata(monkeypatch):
    matching_dict = {
        "table_id": "ga4_events",
        "table_type": "TABLE",
        "creation_time": "2026-06-08T18:38:40Z",
        "last_modified_time": "2026-06-08T18:38:40Z",
        "size_bytes": 576920,
        "size_gb": 0.0005,
        "row_count": 10000,
        "column_count": 1,
        "is_partitioned": False,
        "partition_column": None,
        "is_clustered": False,
        "clustering_columns": [],
        "location": "US",
    }
    monkeypatch.setattr(repository, "get_tables_summary", lambda *a, **k: [matching_dict])
    monkeypatch.setattr(
        repository,
        "get_table_columns",
        lambda *a, **k: [
            {
                "column_name": "event_date",
                "data_type": "STRING",
                "is_nullable": True,
                "description": None,
            }
        ],
    )
    fake_bq_table = SimpleNamespace(labels={"env": "prod"}, description="Eventos GA4")
    client = MagicMock()
    client.get_table.return_value = fake_bq_table

    result = repository.get_table_detail(client, "proj", "RAW", "ga4_events", "US")

    assert result["labels"] == {"env": "prod"}
    assert result["description"] == "Eventos GA4"
    assert result["columns"][0]["column_name"] == "event_date"
    client.get_table.assert_called_once_with("proj.RAW.ga4_events")


def test_get_table_detail_raises_when_table_missing(monkeypatch):
    monkeypatch.setattr(repository, "get_tables_summary", lambda *a, **k: [])

    client = MagicMock()

    with pytest.raises(TableNotFoundError):
        repository.get_table_detail(client, "proj", "RAW", "ghost", "US")
