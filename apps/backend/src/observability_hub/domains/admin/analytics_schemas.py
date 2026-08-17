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


class AccessRequestMonthBucket(BaseModel):
    period: str  # "2026-08"
    total: int
    approved: int
    denied: int
    pending: int


class ProjectRequestCount(BaseModel):
    project_id: str
    request_count: int


class AccessRequestAnalyticsResponse(BaseModel):
    monthly: list[AccessRequestMonthBucket]
    top_projects: list[ProjectRequestCount]
    # None = nenhum pedido resolvido ainda (evita mostrar "0%" quando na
    # verdade não há dado nenhum).
    approval_rate: float | None


class TableViewEntry(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    owner_email: str
    viewed_at: datetime


class SearchEntry(BaseModel):
    query: str
    mode: str
    project_id: str
    owner_email: str
    searched_at: datetime


class NavigationAnalyticsResponse(BaseModel):
    # Listas achatadas — mesmo racional de FavoritesAnalyticsResponse, o
    # front agrega "top tabelas"/"top buscas" a partir do payload bruto.
    # Cada usuário só guarda os 20 itens mais recentes (domains/history),
    # então isso é uma janela recente, não histórico completo.
    table_views: list[TableViewEntry]
    searches: list[SearchEntry]


class PiiScanEntry(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    executed_by: str
    executed_at: datetime
    flagged_columns_count: int


class PiiScanActivityResponse(BaseModel):
    scans: list[PiiScanEntry]
