from datetime import datetime

from pydantic import BaseModel


class FavoriteTable(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    added_at: datetime


class FavoritesListResponse(BaseModel):
    favorites: list[FavoriteTable]


class AddFavoriteRequest(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
