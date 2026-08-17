from datetime import datetime

from pydantic import BaseModel


class Favorite(BaseModel):
    project_id: str
    dataset_id: str
    # None = favorito do dataset inteiro (não uma tabela específica).
    table_id: str | None = None
    nickname: str | None = None
    added_at: datetime


class FavoritesListResponse(BaseModel):
    favorites: list[Favorite]


class AddFavoriteRequest(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str | None = None
    nickname: str | None = None
