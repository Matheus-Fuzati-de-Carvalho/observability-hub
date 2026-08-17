"""Orquestra o domínio favorites: busca via repository, monta os schemas
de response. api/v1/favorites.py só chama estas funções — CLAUDE.md
proíbe lógica de negócio em api/.
"""

from google.cloud import firestore

from observability_hub.domains.favorites import repository
from observability_hub.domains.favorites.schemas import Favorite, FavoritesListResponse


def list_favorites(client: firestore.Client, email: str) -> FavoritesListResponse:
    raw = repository.list_favorites(client, email)
    return FavoritesListResponse(favorites=[Favorite(**f) for f in raw])


def add_favorite(
    client: firestore.Client,
    email: str,
    project_id: str,
    dataset_id: str,
    table_id: str | None = None,
    nickname: str | None = None,
) -> Favorite:
    raw = repository.add_favorite(client, email, project_id, dataset_id, table_id, nickname)
    return Favorite(**raw)


def remove_favorite(
    client: firestore.Client,
    email: str,
    project_id: str,
    dataset_id: str,
    table_id: str | None = None,
) -> None:
    repository.remove_favorite(client, email, project_id, dataset_id, table_id)
