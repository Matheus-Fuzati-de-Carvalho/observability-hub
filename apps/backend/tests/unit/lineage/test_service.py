from unittest.mock import MagicMock

from observability_hub.domains.lineage import service
from observability_hub.domains.lineage.repository import JobEvent


def _event(referenced: list[tuple[str, str, str]], destination: tuple[str, str, str] | None):
    return JobEvent(
        job_id="job1",
        principal_email="a@dp6.com.br",
        referenced_tables=referenced,
        destination_table=destination,
    )


# --- get_table_lineage --------------------------------------------------------


def test_get_table_lineage_finds_upstream_from_jobs_that_wrote_to_target(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads"), ("proj", "RAW", "crm_accounts")],
            destination=("proj", "GOLD", "leads_summary"),
        )
    ]
    monkeypatch.setattr(service.repository, "list_job_events", lambda *a, **kw: events)

    result = service.get_table_lineage(client, logging_client, "proj", "GOLD", "leads_summary")

    assert {(u.dataset_id, u.table_id) for u in result.upstream} == {
        ("RAW", "crm_leads"),
        ("RAW", "crm_accounts"),
    }
    assert result.downstream == []
    assert result.warning is None


def test_get_table_lineage_finds_downstream_from_jobs_that_read_target(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=("proj", "GOLD", "leads_summary"),
        )
    ]
    monkeypatch.setattr(service.repository, "list_job_events", lambda *a, **kw: events)

    result = service.get_table_lineage(client, logging_client, "proj", "RAW", "crm_leads")

    assert result.upstream == []
    assert {(d.dataset_id, d.table_id) for d in result.downstream} == {("GOLD", "leads_summary")}


def test_get_table_lineage_ignores_self_references(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    # Job que só sobrescreve a própria tabela (ex: MERGE) não deveria virar
    # upstream/downstream de si mesma.
    events = [
        _event(referenced=[("proj", "RAW", "crm_leads")], destination=("proj", "RAW", "crm_leads"))
    ]
    monkeypatch.setattr(service.repository, "list_job_events", lambda *a, **kw: events)

    result = service.get_table_lineage(client, logging_client, "proj", "RAW", "crm_leads")

    assert result.upstream == []
    assert result.downstream == []


def test_get_table_lineage_sets_warning_when_no_events(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service.repository, "list_job_events", lambda *a, **kw: [])

    result = service.get_table_lineage(client, logging_client, "proj", "RAW", "crm_leads")

    assert result.upstream == []
    assert result.downstream == []
    assert result.warning is not None
    assert "proj" in result.warning


# --- get_orphans ---------------------------------------------------------------


def test_get_orphans_returns_tables_never_referenced(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "list_all_table_refs",
        lambda *a, **kw: [("RAW", "crm_leads"), ("RAW", "crm_accounts"), ("GOLD", "unused_table")],
    )
    monkeypatch.setattr(
        service.repository,
        "list_job_events",
        lambda *a, **kw: [
            _event(referenced=[("proj", "RAW", "crm_leads")], destination=("proj", "GOLD", "x"))
        ],
    )

    result = service.get_orphans(client, logging_client, "proj")

    orphan_keys = {(o.dataset_id, o.table_id) for o in result.orphans}
    assert orphan_keys == {("RAW", "crm_accounts"), ("GOLD", "unused_table")}
    assert result.warning is None


def test_get_orphans_ignores_referenced_tables_from_other_projects(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "list_all_table_refs", lambda *a, **kw: [("RAW", "crm_leads")]
    )
    monkeypatch.setattr(
        service.repository,
        "list_job_events",
        lambda *a, **kw: [
            _event(referenced=[("other-proj", "RAW", "crm_leads")], destination=None)
        ],
    )

    result = service.get_orphans(client, logging_client, "proj")

    assert {(o.dataset_id, o.table_id) for o in result.orphans} == {("RAW", "crm_leads")}


def test_get_orphans_sets_warning_when_no_events(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "list_all_table_refs", lambda *a, **kw: [("RAW", "crm_leads")]
    )
    monkeypatch.setattr(service.repository, "list_job_events", lambda *a, **kw: [])

    result = service.get_orphans(client, logging_client, "proj")

    assert result.warning is not None
    assert len(result.orphans) == 1
