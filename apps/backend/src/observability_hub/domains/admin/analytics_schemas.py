from datetime import datetime

from pydantic import BaseModel


class LoginEvent(BaseModel):
    email: str
    logged_in_at: datetime


class LoginCountBucket(BaseModel):
    # "2026-08-17" (dia), "2026-W33" (semana ISO) ou "2026-08" (mês).
    period: str
    login_count: int
    unique_users: int


class LoginAnalyticsResponse(BaseModel):
    daily: list[LoginCountBucket]
    weekly: list[LoginCountBucket]
    monthly: list[LoginCountBucket]
    recent_events: list[LoginEvent]


class FavoriteEntry(BaseModel):
    project_id: str
    dataset_id: str
    # None = favorito do dataset inteiro (mesma semântica de domains/favorites).
    table_id: str | None = None
    nickname: str | None = None
    owner_email: str
    added_at: datetime


class FavoritesAnalyticsResponse(BaseModel):
    # Lista achatada — o front agrupa por usuário e por base a partir do
    # mesmo payload (drill-down nos dois sentidos sem precisar de dois
    # endpoints ou de agregação server-side).
    favorites: list[FavoriteEntry]


class ProfilingRunEntry(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    executed_by: str
    executed_at: datetime
    overall_density: float
    estimated_duplicate_pct: float


class ProfilingActivityResponse(BaseModel):
    runs: list[ProfilingRunEntry]
