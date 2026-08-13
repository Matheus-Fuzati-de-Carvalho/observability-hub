from observability_hub.domains.history.schemas import (
    HistoryResponse,
    SearchEvent,
    SearchEventRequest,
    TableViewEvent,
    TableViewRequest,
)


def test_table_view_event_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "dataset_id": "RAW",
        "table_id": "ga4_events",
        "viewed_at": "2026-08-12T03:00:00Z",
    }
    model = TableViewEvent(**payload)
    assert model.table_id == "ga4_events"


def test_search_event_matches_spec_example():
    payload = {
        "query": "events_20260812",
        "mode": "exact",
        "project_id": "observability-hub-dev",
        "searched_at": "2026-08-12T03:00:00Z",
    }
    model = SearchEvent(**payload)
    assert model.query == "events_20260812"


def test_history_response_wraps_both_lists():
    model = HistoryResponse(
        recent_tables=[
            {
                "project_id": "proj",
                "dataset_id": "RAW",
                "table_id": "events",
                "viewed_at": "2026-08-12T03:00:00Z",
            }
        ],
        recent_searches=[
            {
                "query": "events_20260812",
                "mode": "exact",
                "project_id": "proj",
                "searched_at": "2026-08-12T03:00:00Z",
            }
        ],
    )
    assert len(model.recent_tables) == 1
    assert len(model.recent_searches) == 1


def test_table_view_request_requires_all_three_fields():
    request = TableViewRequest(project_id="proj", dataset_id="RAW", table_id="events")
    assert request.table_id == "events"


def test_search_event_request_requires_all_three_fields():
    request = SearchEventRequest(query="events_20260812", mode="exact", project_id="proj")
    assert request.mode == "exact"
