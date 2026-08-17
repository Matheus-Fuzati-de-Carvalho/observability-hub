from datetime import datetime

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
