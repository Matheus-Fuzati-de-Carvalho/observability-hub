from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import (
    InvalidSamplePercentError,
    PiiScanTimeoutError,
    TableNotFoundError,
)
from observability_hub.domains.pii import service, sql_builder
from observability_hub.domains.pii.schemas import PiiScanRequest

EXECUTED_BY = "a@dp6.com.br"


def _fake_client() -> MagicMock:
    return MagicMock(name="bigquery.Client")


def _fake_firestore_client() -> MagicMock:
    return MagicMock(name="firestore.Client")


def _stub_region_resolution(monkeypatch, location="US", is_view=False):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: location,
    )
    monkeypatch.setattr(
        service.repository,
        "is_view",
        lambda client, project_id, dataset_id, table_id, location: is_view,
    )


def _stub_columns(monkeypatch, columns):
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: columns,
    )


def _result_row(column_name: str, non_null: int, **matches: int) -> dict:
    row = {f"{column_name}__non_null": non_null}
    for pii_type in sql_builder.PII_PATTERNS:
        row[f"{column_name}__{pii_type}"] = matches.get(pii_type, 0)
    return row


def _reset_cache(monkeypatch):
    monkeypatch.setattr(service, "_scan_cache", {})
    # history_repository.save_scan grava de verdade num client Firestore —
    # aqui é um MagicMock, cuja iteração em _trim_to_max quebraria sem esse
    # stub. Comportamento de gravação é coberto em
    # tests/unit/pii/test_history_repository.py, não precisa duplicar aqui.
    monkeypatch.setattr(service.history_repository, "save_scan", lambda *args, **kwargs: None)


def run_scan(client, project_id, dataset_id, table_id, request):
    return service.run_pii_scan(
        client, _fake_firestore_client(), project_id, dataset_id, table_id, request, EXECUTED_BY
    )


# --- validation --------------------------------------------------------------


def test_validate_sample_percent_raises_below_one():
    with pytest.raises(InvalidSamplePercentError):
        service._validate_sample_percent(0.5)


def test_run_pii_scan_raises_for_invalid_sample_percent(monkeypatch):
    _reset_cache(monkeypatch)
    with pytest.raises(InvalidSamplePercentError):
        run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest(sample_percent=0.5))


def test_run_pii_scan_raises_table_not_found_when_no_columns(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [])

    with pytest.raises(TableNotFoundError):
        run_scan(_fake_client(), "proj", "RAW", "ghost", PiiScanRequest())


# --- name heuristic ------------------------------------------------------------


def test_run_pii_scan_always_includes_name_heuristic(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _result_row("email_cliente", 100),
    )

    result = run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    column = result.columns[0]
    assert column.name_match_types == ["email"]
    assert column.flagged is True
    assert column.confidence == "medium"  # nome bate, amostra não teve match


# --- limiar de matching --------------------------------------------------------


def test_run_pii_scan_flags_column_exactly_at_threshold(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "contato", "data_type": "STRING"}])
    # 5 de 100 = 5% -> bate exatamente no threshold default (5%)
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _result_row("contato", 100, email=5),
    )

    result = run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    match = result.columns[0].sample_matches[0]
    assert match.match_ratio == 0.05
    assert match.flagged is True
    assert result.columns[0].flagged is True


def test_run_pii_scan_does_not_flag_column_below_threshold(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "contato", "data_type": "STRING"}])
    # 4 de 100 = 4% -> abaixo do threshold default (5%)
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _result_row("contato", 100, email=4),
    )

    result = run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    match = result.columns[0].sample_matches[0]
    assert match.flagged is False
    assert result.columns[0].flagged is False
    assert result.columns[0].confidence is None


def test_run_pii_scan_zero_matches_are_omitted_from_sample_matches(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "descricao", "data_type": "STRING"}])
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _result_row("descricao", 100),
    )

    result = run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    assert result.columns[0].sample_matches == []
    assert result.columns[0].flagged is False


# --- confidence ------------------------------------------------------------------


def test_run_pii_scan_high_confidence_when_name_and_sample_agree(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _result_row("email_cliente", 100, email=50),
    )

    result = run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    assert result.columns[0].confidence == "high"


def test_run_pii_scan_medium_confidence_when_only_sample_flags(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "info_generica", "data_type": "STRING"}])
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _result_row("info_generica", 100, email=50),
    )

    result = run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    assert result.columns[0].name_match_types == []
    assert result.columns[0].confidence == "medium"


# --- exclusão de tipos -----------------------------------------------------------


def test_run_pii_scan_excludes_non_string_columns(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(
        monkeypatch,
        [
            {"column_name": "email_cliente", "data_type": "STRING"},
            {"column_name": "idade", "data_type": "INT64"},
            {"column_name": "endereco", "data_type": "STRUCT<rua STRING>"},
            {"column_name": "tags", "data_type": "ARRAY<STRING>"},
            {"column_name": "foto", "data_type": "BYTES"},
        ],
    )
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _result_row("email_cliente", 10),
    )

    result = run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    assert {c.column_name for c in result.columns} == {"email_cliente"}
    excluded_names = {e.column_name for e in result.excluded_columns}
    assert excluded_names == {"idade", "endereco", "tags", "foto"}


# --- guard de view -----------------------------------------------------------------


def test_run_pii_scan_skips_sampling_for_view(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch, is_view=True)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])
    execute_mock = MagicMock()
    monkeypatch.setattr(service.repository, "execute_scan_query", execute_mock)

    result = run_scan(_fake_client(), "proj", "RAW", "clientes_view", PiiScanRequest())

    execute_mock.assert_not_called()
    assert result.is_view is True
    assert result.sql is None
    assert result.warning is not None
    assert result.columns[0].name_match_types == ["email"]
    assert result.columns[0].sample_non_null_count is None


def test_estimate_pii_scan_returns_zero_cost_for_view(monkeypatch):
    _stub_region_resolution(monkeypatch, is_view=True)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])
    dry_run_mock = MagicMock()
    monkeypatch.setattr(service.repository, "dry_run", dry_run_mock)

    result = service.estimate_pii_scan(
        _fake_client(), "proj", "RAW", "clientes_view", PiiScanRequest()
    )

    dry_run_mock.assert_not_called()
    assert result.estimated_bytes == 0
    assert result.sql is None


# --- sem coluna STRING -------------------------------------------------------------


def test_run_pii_scan_skips_sampling_when_no_string_columns(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "idade", "data_type": "INT64"}])
    execute_mock = MagicMock()
    monkeypatch.setattr(service.repository, "execute_scan_query", execute_mock)

    result = run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    execute_mock.assert_not_called()
    assert result.sql is None
    assert result.columns == []
    assert result.warning is not None


# --- estimativa de custo -----------------------------------------------------------


def test_estimate_pii_scan_returns_dry_run_bytes_and_cost(monkeypatch):
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])
    monkeypatch.setattr(service.repository, "dry_run", lambda client, project_id, sql: 849813)

    result = service.estimate_pii_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())

    assert result.estimated_bytes == 849813
    assert "KB" in result.estimated_bytes_human
    assert "SELECT" in result.sql


# --- cache -----------------------------------------------------------------------


def test_run_pii_scan_caches_by_table_and_parameters(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])
    execute_mock = MagicMock(return_value=_result_row("email_cliente", 10))
    monkeypatch.setattr(service.repository, "execute_scan_query", execute_mock)

    request = PiiScanRequest()
    first = run_scan(_fake_client(), "proj", "RAW", "clientes", request)
    second = run_scan(_fake_client(), "proj", "RAW", "clientes", request)

    assert first == second
    assert execute_mock.call_count == 1


def test_run_pii_scan_does_not_reuse_cache_for_different_parameters(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])
    execute_mock = MagicMock(return_value=_result_row("email_cliente", 10))
    monkeypatch.setattr(service.repository, "execute_scan_query", execute_mock)

    run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest(sample_percent=10))
    run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest(sample_percent=20))

    assert execute_mock.call_count == 2


def test_run_pii_scan_saves_history_on_real_execution_not_on_cache_hit(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])
    monkeypatch.setattr(
        service.repository,
        "execute_scan_query",
        lambda client, project_id, sql, timeout: _result_row("email_cliente", 100, email=50),
    )
    save_scan_mock = MagicMock()
    monkeypatch.setattr(service.history_repository, "save_scan", save_scan_mock)

    request = PiiScanRequest()
    run_scan(_fake_client(), "proj", "RAW", "clientes", request)
    run_scan(_fake_client(), "proj", "RAW", "clientes", request)  # cache hit

    save_scan_mock.assert_called_once()
    _, kwargs = save_scan_mock.call_args
    assert kwargs["executed_by"] == EXECUTED_BY
    assert kwargs["flagged_columns_count"] == 1


# --- timeout -----------------------------------------------------------------------


def test_run_pii_scan_raises_pii_scan_timeout_on_timeout_error(monkeypatch):
    _reset_cache(monkeypatch)
    _stub_region_resolution(monkeypatch)
    _stub_columns(monkeypatch, [{"column_name": "email_cliente", "data_type": "STRING"}])

    def _raise_timeout(client, project_id, sql, timeout):
        raise TimeoutError("deadline exceeded")

    monkeypatch.setattr(service.repository, "execute_scan_query", _raise_timeout)

    with pytest.raises(PiiScanTimeoutError):
        run_scan(_fake_client(), "proj", "RAW", "clientes", PiiScanRequest())
