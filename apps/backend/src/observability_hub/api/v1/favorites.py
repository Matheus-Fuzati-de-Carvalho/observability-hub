from fastapi import APIRouter, Depends
from google.cloud import firestore

from observability_hub.core.auth import get_current_user
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.auth.schemas import UserInfo
from observability_hub.domains.favorites import service
from observability_hub.domains.favorites.schemas import (
    AddFavoriteRequest,
    Favorite,
    FavoritesListResponse,
)

router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])


@router.get("", response_model=FavoritesListResponse)
def list_favorites(
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> FavoritesListResponse:
    return service.list_favorites(client, user.email)


@router.post("", response_model=Favorite)
def add_favorite(
    request: AddFavoriteRequest,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> Favorite:
    return service.add_favorite(
        client,
        user.email,
        request.project_id,
        request.dataset_id,
        request.table_id,
        request.nickname,
    )


@router.delete("/{project_id}/{dataset_id}/{table_id}", status_code=204)
def remove_table_favorite(
    project_id: str,
    dataset_id: str,
    table_id: str,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.remove_favorite(client, user.email, project_id, dataset_id, table_id)


@router.delete("/{project_id}/{dataset_id}", status_code=204)
def remove_dataset_favorite(
    project_id: str,
    dataset_id: str,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.remove_favorite(client, user.email, project_id, dataset_id, table_id=None)
