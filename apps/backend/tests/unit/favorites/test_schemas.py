from observability_hub.domains.favorites.schemas import (
    AddFavoriteRequest,
    Favorite,
    FavoritesListResponse,
)


def test_favorite_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "dataset_id": "RAW",
        "table_id": "ga4_events",
        "added_at": "2026-08-12T03:00:00Z",
    }
    model = Favorite(**payload)
    assert model.table_id == "ga4_events"
    assert model.nickname is None


def test_favorite_table_id_defaults_to_none_for_dataset_level():
    model = Favorite(
        project_id="proj",
        dataset_id="RAW",
        added_at="2026-08-12T03:00:00Z",
    )
    assert model.table_id is None


def test_favorite_accepts_nickname():
    model = Favorite(
        project_id="proj",
        dataset_id="RAW",
        table_id="events",
        nickname="Meu apelido",
        added_at="2026-08-12T03:00:00Z",
    )
    assert model.nickname == "Meu apelido"


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


def test_add_favorite_request_requires_only_project_and_dataset():
    request = AddFavoriteRequest(project_id="proj", dataset_id="RAW")
    assert request.table_id is None
    assert request.nickname is None


def test_add_favorite_request_accepts_table_id_and_nickname():
    request = AddFavoriteRequest(
        project_id="proj", dataset_id="RAW", table_id="events", nickname="Apelido"
    )
    assert request.table_id == "events"
    assert request.nickname == "Apelido"
