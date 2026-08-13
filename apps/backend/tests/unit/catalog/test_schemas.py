from datetime import UTC, datetime

from observability_hub.domains.catalog.schemas import (
    ColumnDetail,
    DatasetsListResponse,
    DatasetSummary,
    PartitionRow,
    ProjectValidateResponse,
    TableDetail,
    TablePartitionsResponse,
    TableSearchResponse,
    TablesListResponse,
    TableSummary,
    TableType,
)


def test_project_validate_response_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "accessible": True,
        "available_regions": ["US"],
        "total_datasets": 3,
        "is_native": True,
    }
    model = ProjectValidateResponse(**payload)
    assert model.model_dump() == payload


def test_dataset_summary_matches_spec_example():
    payload = {
        "dataset_id": "RAW",
        "location": "US",
        "creation_time": "2026-06-03T19:40:00Z",
        "last_modified_time": "2026-06-08T18:38:00Z",
        "total_tables": 3,
        "total_views": 0,
        "total_size_bytes": 2075443,
        "total_size_gb": 0.002,
        "total_rows": 30000,
    }
    model = DatasetSummary(**payload)
    assert model.dataset_id == "RAW"
    assert model.total_size_gb == 0.002
    assert model.creation_time == datetime(2026, 6, 3, 19, 40, tzinfo=UTC)


def test_datasets_list_response_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "evaluated_at": "2026-08-05T10:00:00Z",
        "total_datasets": 1,
        "regions_found": ["US"],
        "datasets": [
            {
                "dataset_id": "RAW",
                "location": "US",
                "creation_time": "2026-06-03T19:40:00Z",
                "last_modified_time": "2026-06-08T18:38:00Z",
                "total_tables": 3,
                "total_views": 0,
                "total_size_bytes": 2075443,
                "total_size_gb": 0.002,
                "total_rows": 30000,
            }
        ],
    }
    model = DatasetsListResponse(**payload)
    assert model.total_datasets == 1
    assert len(model.datasets) == 1


def test_table_summary_matches_spec_example():
    payload = {
        "table_id": "ga4_events",
        "table_type": "TABLE",
        "creation_time": "2026-06-08T18:38:40Z",
        "last_modified_time": "2026-06-08T18:38:40Z",
        "size_bytes": 576920,
        "size_gb": 0.0005,
        "row_count": 10000,
        "column_count": 8,
        "is_partitioned": False,
        "partition_column": None,
        "is_clustered": False,
        "clustering_columns": [],
        "location": "US",
    }
    model = TableSummary(**payload)
    assert model.table_type == "TABLE"
    assert model.partition_column is None


def test_table_summary_allows_null_size_for_view_or_external():
    payload = {
        "table_id": "v_events",
        "table_type": "VIEW",
        "creation_time": "2026-06-08T18:38:40Z",
        "last_modified_time": "2026-06-08T18:38:40Z",
        "size_bytes": None,
        "size_gb": None,
        "row_count": None,
        "column_count": 5,
        "is_partitioned": False,
        "partition_column": None,
        "is_clustered": False,
        "clustering_columns": [],
        "location": "US",
    }
    model = TableSummary(**payload)
    assert model.size_bytes is None
    assert model.row_count is None


def test_tables_list_response_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "dataset_id": "RAW",
        "location": "US",
        "total_tables": 1,
        "tables": [
            {
                "table_id": "ga4_events",
                "table_type": "TABLE",
                "creation_time": "2026-06-08T18:38:40Z",
                "last_modified_time": "2026-06-08T18:38:40Z",
                "size_bytes": 576920,
                "size_gb": 0.0005,
                "row_count": 10000,
                "column_count": 8,
                "is_partitioned": False,
                "partition_column": None,
                "is_clustered": False,
                "clustering_columns": [],
                "location": "US",
            }
        ],
    }
    model = TablesListResponse(**payload)
    assert model.total_tables == 1


def test_column_detail_matches_spec_example():
    payload = {
        "column_name": "event_date",
        "data_type": "STRING",
        "is_nullable": True,
        "description": None,
    }
    model = ColumnDetail(**payload)
    assert model.column_name == "event_date"


def test_table_detail_matches_spec_example():
    payload = {
        "table_id": "ga4_events",
        "table_type": "TABLE",
        "creation_time": "2026-06-08T18:38:40Z",
        "last_modified_time": "2026-06-08T18:38:40Z",
        "size_bytes": 576920,
        "size_gb": 0.0005,
        "row_count": 10000,
        "column_count": 8,
        "is_partitioned": False,
        "partition_column": None,
        "is_clustered": False,
        "clustering_columns": [],
        "location": "US",
        "columns": [
            {
                "column_name": "event_date",
                "data_type": "STRING",
                "is_nullable": True,
                "description": None,
            }
        ],
        "labels": {},
        "description": None,
    }
    model = TableDetail(**payload)
    assert len(model.columns) == 1
    assert model.labels == {}


def test_table_partitions_response_matches_spec_example():
    payload = {
        "table_id": "events",
        "partition_column": "event_date",
        "partition_type": "event_date (DAY)",
        "total_partitions": 2,
        "partitions": [
            {"value": "2026-08-12", "row_count": 1800},
            {"value": "2026-08-11", "row_count": 1500},
        ],
    }
    model = TablePartitionsResponse(**payload)
    assert model.total_partitions == 2
    assert model.partitions[0] == PartitionRow(value="2026-08-12", row_count=1800)


def test_table_search_response_matches_spec_example():
    payload = {
        "query": "events_20260812",
        "mode": "exact",
        "project_id": "cliente-x-prod",
        "datasets_with_match": [
            {
                "dataset_id": "analytics_123",
                "table_id": "events_20260812",
                "table_type": "TABLE",
                "last_modified_time": "2026-08-12T03:00:00Z",
                "row_count": 22096,
            }
        ],
        "datasets_without_match": [
            {
                "dataset_id": "analytics_456",
                "reason": "prefix_exists",
                "latest_partition": "events_20260810",
            },
            {
                "dataset_id": "analytics_789",
                "reason": "prefix_exists",
                "latest_partition": "events_20260809",
            },
        ],
    }
    model = TableSearchResponse(**payload)
    assert model.mode.value == "exact"
    assert len(model.datasets_with_match) == 1
    assert len(model.datasets_without_match) == 2


def test_table_type_enum_values():
    assert TableType.TABLE.value == "TABLE"
    assert TableType.MATERIALIZED_VIEW.value == "MATERIALIZED_VIEW"
    assert {t.value for t in TableType} == {"TABLE", "VIEW", "EXTERNAL", "MATERIALIZED_VIEW"}
