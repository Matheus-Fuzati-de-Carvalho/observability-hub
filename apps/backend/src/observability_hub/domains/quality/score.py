"""Cálculo puro do score de qualidade — nenhuma função aqui toca
BigQuery/Firestore, só recebe os dados já resolvidos por service.py e
devolve o score + breakdown. Mesmo racional de sql_builder.py neste
domínio: lógica pura, fácil de testar sem mocks de client.
"""

from dataclasses import dataclass

COMPLETENESS_WEIGHT = 0.40
FRESHNESS_WEIGHT = 0.30
DUPLICATES_WEIGHT = 0.20
DOCUMENTATION_WEIGHT = 0.10

_NEUTRAL_SCORE = 50.0

_FRESHNESS_SCORE_BY_SLA_STATUS = {
    "ok": 100.0,
    "warning_12_24": 80.0,
    "warning_24_48": 60.0,
    "warning_48_7d": 40.0,
    "warning_7d_1m": 20.0,
    "stale": 0.0,
}


@dataclass(frozen=True)
class LastProfilingResult:
    overall_density: float
    estimated_duplicate_pct: float


@dataclass(frozen=True)
class ScoreBreakdown:
    completeness: float
    freshness: float
    duplicates: float
    documentation: float


@dataclass(frozen=True)
class QualityScore:
    score: int
    breakdown: ScoreBreakdown
    has_profiling_data: bool


def _completeness_score(profiling_result: LastProfilingResult | None) -> float:
    if profiling_result is None:
        return _NEUTRAL_SCORE
    return profiling_result.overall_density


def _duplicates_score(profiling_result: LastProfilingResult | None) -> float:
    """0% -> 100 | 1-5% -> 80 | 5-10% -> 60 | >10% -> 40 (spec Sprint 3.2)."""
    if profiling_result is None:
        return _NEUTRAL_SCORE
    pct = profiling_result.estimated_duplicate_pct
    if pct == 0:
        return 100.0
    if pct <= 5:
        return 80.0
    if pct <= 10:
        return 60.0
    return 40.0


def _freshness_score(sla_status: str | None) -> float:
    if sla_status is None:
        return _NEUTRAL_SCORE
    return _FRESHNESS_SCORE_BY_SLA_STATUS[sla_status]


def _documentation_score(description: str | None) -> float:
    return 100.0 if description else 0.0


def calculate_score(
    profiling_result: LastProfilingResult | None,
    sla_status: str | None,
    description: str | None,
) -> QualityScore:
    completeness = _completeness_score(profiling_result)
    freshness = _freshness_score(sla_status)
    duplicates = _duplicates_score(profiling_result)
    documentation = _documentation_score(description)

    weighted = (
        completeness * COMPLETENESS_WEIGHT
        + freshness * FRESHNESS_WEIGHT
        + duplicates * DUPLICATES_WEIGHT
        + documentation * DOCUMENTATION_WEIGHT
    )

    return QualityScore(
        score=round(weighted),
        breakdown=ScoreBreakdown(
            completeness=completeness,
            freshness=freshness,
            duplicates=duplicates,
            documentation=documentation,
        ),
        has_profiling_data=profiling_result is not None,
    )
