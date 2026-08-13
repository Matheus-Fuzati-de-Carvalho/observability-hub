from observability_hub.domains.favorites.schemas import (
    AddFavoriteRequest,
    FavoritesListResponse,
    FavoriteTable,
)


def test_favorite_table_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "dataset_id": "RAW",
        "table_id": "ga4_events",
        "added_at": "2026-08-12T03:00:00Z",
    }
    model = FavoriteTable(**payload)
    assert model.table_id == "ga4_events"


def test_favorites_list_response_wraps_list():
    model = FavoritesListResponse(
        favorites=[
            {
                "project_id": "proj",
                "dataset_id": "RAW",
                "table_id": "events",
                "added_at": "2026-08-12T03:00:00Z",
            }
        ]
    )
    assert len(model.favorites) == 1


def test_add_favorite_request_requires_all_three_fields():
    request = AddFavoriteRequest(project_id="proj", dataset_id="RAW", table_id="events")
    assert request.table_id == "events"
