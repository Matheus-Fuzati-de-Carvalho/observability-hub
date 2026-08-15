from datetime import UTC, datetime
from unittest.mock import MagicMock

from observability_hub.domains.access import service
from observability_hub.domains.access.repository import AccessEvent


def _event(
    referenced,
    destination,
    principal_email="user@dp6.com.br",
    timestamp=datetime(2026, 8, 14, 10, 0, tzinfo=UTC),
    job_id="job1",
):
    return AccessEvent(
        job_id=job_id,
        principal_email=principal_email,
        timestamp=timestamp,
        referenced_tables=referenced,
        destination_table=destination,
    )


def _events(monkeypatch, events, hub_project="hub-proj"):
    monkeypatch.setattr(service.repository, "list_access_events", lambda *a, **kw: events)
    # get_client() nunca deve ser chamado de verdade em teste unitário —
    # _hub_runtime_sa_email() só lê .project, então um MagicMock com esse
    # atributo já basta (ver core/bigquery.py::get_client, singleton via
    # lru_cache, não usado aqui de outra forma).
    monkeypatch.setattr(service, "get_client", lambda: MagicMock(project=hub_project))


# --- read/write classification ------------------------------------------------


def test_get_table_access_counts_read_access(monkeypatch):
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=("proj", "GOLD", "leads_summary"),
        )
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert len(result.users) == 1
    assert result.users[0].access_types == ["read"]
    assert result.users[0].access_count == 1


def test_get_table_access_counts_write_access(monkeypatch):
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=("proj", "GOLD", "leads_summary"),
        )
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "GOLD", "leads_summary")

    assert len(result.users) == 1
    assert result.users[0].access_types == ["write"]


def test_get_table_access_counts_both_read_and_write_for_self_referencing_job(monkeypatch):
    # MERGE que lê e escreve na mesma tabela: acesso real, diferente do
    # lineage (que exclui auto-referência por não representar dependência
    # entre tabelas).
    events = [
        _event(referenced=[("proj", "RAW", "crm_leads")], destination=("proj", "RAW", "crm_leads"))
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert len(result.users) == 1
    assert set(result.users[0].access_types) == {"read", "write"}
    assert result.users[0].access_count == 1


def test_get_table_access_ignores_unrelated_tables(monkeypatch):
    events = [
        _event(referenced=[("proj", "RAW", "other_table")], destination=None),
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert result.users == []


def test_get_table_access_ignores_same_named_table_from_other_project(monkeypatch):
    events = [_event(referenced=[("other-proj", "RAW", "crm_leads")], destination=None)]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert result.users == []


# --- agregação por principal -----------------------------------------------------


def test_get_table_access_aggregates_multiple_events_from_same_principal(monkeypatch):
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="ana@dp6.com.br",
            timestamp=datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
            job_id="job1",
        ),
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="ana@dp6.com.br",
            timestamp=datetime(2026, 8, 14, 9, 0, tzinfo=UTC),
            job_id="job2",
        ),
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert len(result.users) == 1
    assert result.users[0].access_count == 2
    assert result.users[0].last_accessed_at == datetime(2026, 8, 14, 9, 0, tzinfo=UTC)


def test_get_table_access_sorts_users_by_most_recent_access(monkeypatch):
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="old@dp6.com.br",
            timestamp=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        ),
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="recent@dp6.com.br",
            timestamp=datetime(2026, 8, 14, 10, 0, tzinfo=UTC),
        ),
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert [u.principal_email for u in result.users] == ["recent@dp6.com.br", "old@dp6.com.br"]


def test_get_table_access_respects_limit(monkeypatch):
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email=f"user{i}@dp6.com.br",
            timestamp=datetime(2026, 8, i + 1, 10, 0, tzinfo=UTC),
        )
        for i in range(5)
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads", limit=2)

    assert len(result.users) == 2
    assert result.users[0].principal_email == "user4@dp6.com.br"


# --- humano vs service account ----------------------------------------------------


def test_get_table_access_classifies_service_account(monkeypatch):
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="backend-run@proj.iam.gserviceaccount.com",
        )
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert result.users[0].is_service_account is True


def test_get_table_access_classifies_human_user(monkeypatch):
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="ana@dp6.com.br",
        )
    ]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert result.users[0].is_service_account is False


# --- timestamp ausente e resultado vazio ------------------------------------------


def test_get_table_access_skips_events_without_timestamp(monkeypatch):
    events = [_event(referenced=[("proj", "RAW", "crm_leads")], destination=None, timestamp=None)]
    _events(monkeypatch, events)

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert result.users == []
    assert result.warning is None  # events não está vazio, só não teve timestamp válido


def test_get_table_access_sets_warning_when_no_events(monkeypatch):
    _events(monkeypatch, [])

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert result.users == []
    assert result.warning is not None
    assert "proj" in result.warning


# --- exclusão da SA de runtime do próprio Hub -------------------------------------


def test_get_table_access_excludes_hub_own_runtime_service_account(monkeypatch):
    # Toda vez que o usuário roda profiling/PII pela UI, quem executa a
    # query real é a SA de runtime do Hub — não deve aparecer como um
    # "acesso" externo real.
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="backend-run@hub-proj.iam.gserviceaccount.com",
        ),
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="ana@dp6.com.br",
        ),
    ]
    _events(monkeypatch, events, hub_project="hub-proj")

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert [u.principal_email for u in result.users] == ["ana@dp6.com.br"]


def test_get_table_access_does_not_exclude_other_service_accounts(monkeypatch):
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=None,
            principal_email="glue-job@other-proj.iam.gserviceaccount.com",
        )
    ]
    _events(monkeypatch, events, hub_project="hub-proj")

    result = service.get_table_access(MagicMock(), "proj", "RAW", "crm_leads")

    assert len(result.users) == 1
    assert result.users[0].principal_email == "glue-job@other-proj.iam.gserviceaccount.com"
    assert result.users[0].is_service_account is True
