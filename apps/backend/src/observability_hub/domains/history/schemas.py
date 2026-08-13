from datetime import datetime

from pydantic import BaseModel


class TableViewEvent(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    viewed_at: datetime


class SearchEvent(BaseModel):
    query: str
    mode: str
    project_id: str
    searched_at: datetime


class HistoryResponse(BaseModel):
    recent_tables: list[TableViewEvent]
    recent_searches: list[SearchEvent]


class TableViewRequest(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str


class SearchEventRequest(BaseModel):
    query: str
    mode: str
    project_id: str
