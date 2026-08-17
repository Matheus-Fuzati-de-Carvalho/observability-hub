from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class HubUser(BaseModel):
    email: str
    is_admin: bool = False
    # "*" (literal) libera qualquer project_id que a service account de
    # runtime alcançar — ver domains/admin/service.py::has_project_access.
    allowed_projects: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    updated_by: str


class HubUsersListResponse(BaseModel):
    users: list[HubUser]


class UpsertHubUserRequest(BaseModel):
    is_admin: bool = False
    allowed_projects: list[str] = Field(default_factory=list)


class HubProject(BaseModel):
    project_id: str
    # Libera o projeto pra QUALQUER usuário do Hub, inclusive quem ainda
    # não tem doc em hub_users (usuário futuro) — eixo independente do
    # allowed_projects de cada usuário, ver
    # domains/admin/service.py::has_project_access.
    is_public: bool = False
    created_at: datetime
    updated_at: datetime
    updated_by: str


class HubProjectsListResponse(BaseModel):
    projects: list[HubProject]


class UpsertHubProjectRequest(BaseModel):
    is_public: bool = False


class ProjectAccessGrant(BaseModel):
    email: str
    is_admin: bool
    # "wildcard" = tem "*" em allowed_projects (acesso a tudo, não só
    # este projeto); "explicit" = este project_id está listado nominalmente.
    granted_via: Literal["explicit", "wildcard"]


class ProjectUsersResponse(BaseModel):
    project_id: str
    is_public: bool
    users: list[ProjectAccessGrant]


class AccessRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class AccessRequest(BaseModel):
    request_id: str
    email: str
    project_id: str
    status: AccessRequestStatus
    requested_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class AccessRequestsListResponse(BaseModel):
    requests: list[AccessRequest]


class CreateAccessRequestsRequest(BaseModel):
    project_ids: list[str] = Field(default_factory=list)
