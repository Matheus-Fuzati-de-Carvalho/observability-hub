from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel


class MinDaysUnused(IntEnum):
    """IntEnum, não Literal[int,...] — mesma correção já aplicada em
    domains/finops/schemas.py (Literal não faz coerção de string pra int
    em query param, causava 422). Duplicado aqui de propósito — domínios
    não importam um do outro (CLAUDE.md)."""

    THIRTY = 30
    SIXTY = 60
    NINETY = 90


class BucketSummary(BaseModel):
    name: str
    location: str
    storage_class: str
    total_size_bytes: int
    object_count: int
    has_lifecycle_rule: bool
    # Metadado nativo do bucket (Bucket.time_created/Bucket.updated), já
    # vem de graça em list_buckets() — sem chamada extra. "updated" é
    # quando a CONFIGURAÇÃO do bucket mudou (lifecycle, storage class...),
    # não quando um objeto foi gravado — diferente do "last_modified" que
    # a v1 desta spec calculava a partir de customTime/updated dos objetos.
    time_created: datetime
    updated: datetime


class BucketsListResponse(BaseModel):
    buckets: list[BucketSummary]


class WasteCandidate(BaseModel):
    bucket_name: str
    eligible_object_count: int
    eligible_size_bytes: int
    oldest_object_age_days: int
    estimated_savings_usd_month_min: float
    estimated_savings_usd_month_max: float


class WasteCandidatesResponse(BaseModel):
    project_id: str
    min_days_unused: MinDaysUnused
    candidates: list[WasteCandidate]
    savings_disclaimer: str
    limitation: str
