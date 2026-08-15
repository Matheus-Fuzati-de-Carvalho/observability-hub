"""Classificação de SLA de freshness (limiares em horas desde a última
atualização) — vive em core/ porque é usada por dois domínios (freshness,
que já usava isso, e quality, que precisa da mesma classificação pro
score de qualidade). Extraído de domains/freshness/repository.py pra
evitar um domínio importar símbolo privado do outro.
"""

from datetime import UTC, datetime

_SLA_THRESHOLDS_HOURS = [
    (12, "ok"),
    (24, "warning_12_24"),
    (48, "warning_24_48"),
    (168, "warning_48_7d"),
    (720, "warning_7d_1m"),
]


def hours_since(modified: datetime | None) -> float | None:
    if modified is None:
        return None
    return (datetime.now(UTC) - modified).total_seconds() / 3600


def sla_status(hours_since_update: float | None) -> str | None:
    if hours_since_update is None:
        return None
    for threshold, status in _SLA_THRESHOLDS_HOURS:
        if hours_since_update <= threshold:
            return status
    return "stale"
