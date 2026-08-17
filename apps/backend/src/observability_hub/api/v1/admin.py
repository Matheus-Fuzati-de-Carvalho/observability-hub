from fastapi import APIRouter, Depends, Query
from google.cloud import firestore

from observability_hub.core.auth import require_admin
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.admin import analytics_service, service
from observability_hub.domains.admin.analytics_schemas import (
    AccessRequestAnalyticsResponse,
    FavoritesAnalyticsResponse,
    LoginAnalyticsResponse,
    NavigationAnalyticsResponse,
    PiiScanActivityResponse,
    ProfilingActivityResponse,
)
from observability_hub.domains.admin.schemas import (
    AccessRequest,
    AccessRequestsListResponse,
    AccessRequestStatus,
    HubProject,
    HubProjectsListResponse,
    HubUser,
    HubUsersListResponse,
    ProjectUsersResponse,
    UpsertHubProjectRequest,
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


@router.get("/projects", response_model=HubProjectsListResponse)
def list_projects(
    client: firestore.Client = Depends(get_firestore_client),
) -> HubProjectsListResponse:
    return service.list_projects(client)


@router.put("/projects/{project_id}", response_model=HubProject)
def upsert_project(
    project_id: str,
    request: UpsertHubProjectRequest,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> HubProject:
    return service.upsert_project(client, project_id, request, updated_by=admin_user.email)


@router.get("/projects/{project_id}/users", response_model=ProjectUsersResponse)
def get_project_users(
    project_id: str,
    client: firestore.Client = Depends(get_firestore_client),
) -> ProjectUsersResponse:
    return service.get_project_users(client, project_id)


@router.post("/projects/{project_id}/users/{email}", response_model=HubUser)
def grant_project(
    project_id: str,
    email: str,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> HubUser:
    return service.grant_project_to_user(client, project_id, email, updated_by=admin_user.email)


@router.delete("/projects/{project_id}/users/{email}", status_code=204)
def revoke_project(
    project_id: str,
    email: str,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.revoke_project_from_user(client, project_id, email, updated_by=admin_user.email)


@router.get("/access-requests", response_model=AccessRequestsListResponse)
def list_access_requests(
    status: AccessRequestStatus | None = Query(default=None),
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequestsListResponse:
    return service.list_access_requests(client, status.value if status else None)


@router.post("/access-requests/{request_id}/approve", response_model=AccessRequest)
def approve_access_request(
    request_id: str,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequest:
    return service.approve_access_request(client, request_id, resolved_by=admin_user.email)


@router.post("/access-requests/{request_id}/deny", response_model=AccessRequest)
def deny_access_request(
    request_id: str,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequest:
    return service.deny_access_request(client, request_id, resolved_by=admin_user.email)


@router.get("/analytics/logins", response_model=LoginAnalyticsResponse)
def login_analytics(
    lookback_days: int = Query(default=90, ge=1, le=365),
    client: firestore.Client = Depends(get_firestore_client),
) -> LoginAnalyticsResponse:
    return analytics_service.get_login_analytics(client, lookback_days)


@router.get("/analytics/favorites", response_model=FavoritesAnalyticsResponse)
def favorites_analytics(
    client: firestore.Client = Depends(get_firestore_client),
) -> FavoritesAnalyticsResponse:
    return analytics_service.get_favorites_analytics(client)


@router.get("/analytics/profiling", response_model=ProfilingActivityResponse)
def profiling_activity(
    limit: int = Query(default=200, ge=1, le=1000),
    client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingActivityResponse:
    return analytics_service.get_profiling_activity(client, limit)


@router.get("/analytics/access-requests", response_model=AccessRequestAnalyticsResponse)
def access_request_analytics(
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequestAnalyticsResponse:
    return analytics_service.get_access_request_analytics(client)


@router.get("/analytics/navigation", response_model=NavigationAnalyticsResponse)
def navigation_analytics(
    client: firestore.Client = Depends(get_firestore_client),
) -> NavigationAnalyticsResponse:
    return analytics_service.get_navigation_analytics(client)


@router.get("/analytics/pii-scans", response_model=PiiScanActivityResponse)
def pii_scan_activity(
    limit: int = Query(default=200, ge=1, le=1000),
    client: firestore.Client = Depends(get_firestore_client),
) -> PiiScanActivityResponse:
    return analytics_service.get_pii_scan_activity(client, limit)
