from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PiiType(str, Enum):
    EMAIL = "email"
    CPF = "cpf"
    CNPJ = "cnpj"
    TELEFONE_BR = "telefone_br"
    CEP = "cep"
    CARTAO_CREDITO = "cartao_credito"


class PiiScanRequest(BaseModel):
    sample_percent: float = 10
    match_threshold_pct: float = Field(default=5, ge=0, le=100)


class PiiEstimateResponse(BaseModel):
    estimated_bytes: int
    estimated_bytes_human: str
    estimated_cost_usd: float
    sql: str | None = None


class PiiTypeMatch(BaseModel):
    pii_type: PiiType
    match_count: int
    match_ratio: float
    flagged: bool


class PiiColumnResult(BaseModel):
    column_name: str
    data_type: str
    name_match_types: list[PiiType]
    sample_non_null_count: int | None
    sample_matches: list[PiiTypeMatch]
    flagged: bool
    confidence: Literal["high", "medium"] | None


class PiiExcludedColumn(BaseModel):
    column_name: str
    reason: str


class PiiScanResponse(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    executed_at: datetime
    is_view: bool
    parameters: PiiScanRequest
    sql: str | None
    columns: list[PiiColumnResult]
    excluded_columns: list[PiiExcludedColumn]
    warning: str | None = None
