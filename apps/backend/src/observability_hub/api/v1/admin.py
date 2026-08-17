from fastapi import APIRouter, Depends
from google.cloud import firestore

from observability_hub.core.auth import require_admin
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.admin import service
from observability_hub.domains.admin.schemas import (
    HubUser,
    HubUsersListResponse,
    UpsertHubUserRequest,
)
from observability_hub.domains.auth.schemas import UserInfo

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=HubUsersListResponse)
def list_users(client: firestore.Client = Depends(get_firestore_client)) -> HubUsersListResponse:
    return service.list_users(client)


@router.put("/users/{email}", response_model=HubUser)
def upsert_user(
    email: str,
    request: UpsertHubUserRequest,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> HubUser:
    return service.upsert_user(client, email, request, updated_by=admin_user.email)


@router.delete("/users/{email}", status_code=204)
def delete_user(
    email: str,
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.delete_user(client, email)
