from datetime import datetime
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel

WasteConfidence = Literal["config_based", "usage_confirmed"]


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
    # Subconjunto de eligible_object_count/eligible_size_bytes sem nenhuma
    # leitura registrada nos audit logs do GCS na janela (seção 6.2) — 0
    # quando a checagem 6.2 não rodou nesta resposta (ver
    # WasteCandidatesResponse.usage_check_warning).
    usage_confirmed_object_count: int
    usage_confirmed_size_bytes: int
    # "usage_confirmed" só quando TODOS os objetos elegíveis do bucket
    # estão sem leitura confirmada — um bucket com leitura mista
    # (alguns lidos, outros não) fica "config_based", mesmo que a
    # checagem 6.2 tenha rodado com sucesso.
    confidence: WasteConfidence


class WasteCandidatesResponse(BaseModel):
    project_id: str
    min_days_unused: MinDaysUnused
    candidates: list[WasteCandidate]
    savings_disclaimer: str
    # None quando a checagem 6.2 rodou com sinal confiável (audit log com
    # pelo menos um evento no projeto). Preenchido quando 6.2 não pôde
    # rodar (Forbidden — falta logging.viewer/privateLogViewer) OU quando
    # rodou mas voltou vazia pro projeto inteiro (ambíguo: pode ser zero
    # leituras reais ou DATA_READ do GCS desabilitado) — nesses casos
    # nenhum candidato desta resposta recebe "usage_confirmed".
    usage_check_warning: str | None
