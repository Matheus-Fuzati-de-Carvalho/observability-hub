from datetime import UTC, datetime

from google.cloud import logging as cloud_logging
from google.cloud import storage

from observability_hub.core.config import settings
from observability_hub.core.exceptions import LoggingAccessDeniedError
from observability_hub.domains.storage import repository
from observability_hub.domains.storage.schemas import (
    BucketsListResponse,
    BucketSummary,
    MinDaysUnused,
    WasteCandidate,
    WasteCandidatesResponse,
)

_USAGE_CHECK_LOOKBACK_DAYS = 90

_SAVINGS_DISCLAIMER = (
    "Faixa calculada sobre bytes reais armazenados nos objetos elegíveis "
    "(STANDARD, mais antigos que o threshold), não sobre suposição de "
    "padrão de acesso. Mínimo assume migração pra NEARLINE (mais "
    "conservadora); máximo assume COLDLINE (mais agressiva). ARCHIVE fica "
    "de fora de propósito — custo de retrieval e duração mínima de 365 "
    "dias tornam a recomendação automática arriscada."
)

_USAGE_CHECK_FORBIDDEN_WARNING = (
    "Não foi possível verificar leituras de objeto: a service account do "
    "Hub não tem acesso aos audit logs deste projeto (roles/"
    "logging.viewer + roles/logging.privateLogViewer). Todos os "
    'candidatos abaixo usam só a checagem de configuração ("confidence": '
    '"config_based").'
)

_USAGE_CHECK_EMPTY_WARNING = (
    "Nenhuma leitura de objeto encontrada nos audit logs dos últimos "
    "{days} dias. Isso pode significar (a) que realmente não houve "
    "leitura na janela, ou (b) que o Data Access audit log DATA_READ do "
    "Cloud Storage está desabilitado neste projeto — config separada da "
    "usada pelo BigQuery, ver docs/onboarding-cliente.md. Por segurança, "
    "todos os candidatos abaixo usam só a checagem de configuração "
    '("confidence": "config_based") até essa ambiguidade ser resolvida.'
)


def list_buckets(client: storage.Client, project_id: str) -> BucketsListResponse:
    buckets = repository.list_buckets(client, project_id)
    sizes_and_counts = repository.get_buckets_sizes_and_counts(
        client, project_id, [bucket.name for bucket in buckets]
    )
    return BucketsListResponse(
        buckets=[
            BucketSummary(
                name=bucket.name,
                location=bucket.location or "",
                storage_class=bucket.storage_class or "",
                total_size_bytes=sizes_and_counts[bucket.name][0],
                object_count=sizes_and_counts[bucket.name][1],
                has_lifecycle_rule=_has_lifecycle_rule(bucket),
                time_created=bucket.time_created,
                updated=bucket.updated,
            )
            for bucket in buckets
        ]
    )


def get_waste_candidates(
    client: storage.Client,
    logging_client: cloud_logging.Client,
    project_id: str,
    min_days_unused: MinDaysUnused,
) -> WasteCandidatesResponse:
    now = datetime.now(UTC)
    buckets = [
        bucket
        for bucket in repository.list_buckets(client, project_id)
        if not _has_lifecycle_rule(bucket)
    ]

    eligible_by_bucket = {
        bucket.name: repository.get_eligible_waste_objects(
            client, project_id, bucket.name, int(min_days_unused), now
        )
        for bucket in buckets
    }
    eligible_by_bucket = {name: blobs for name, blobs in eligible_by_bucket.items() if blobs}

    read_keys, usage_check_warning = _read_object_keys_or_warning(logging_client, project_id)

    candidates = []
    for bucket_name, eligible in eligible_by_bucket.items():
        size_bytes = sum(blob.size or 0 for blob in eligible)
        oldest_age_days = max((now - (blob.custom_time or blob.updated)).days for blob in eligible)
        unread = [blob for blob in eligible if (bucket_name, blob.name) not in read_keys]
        usage_confirmed_size_bytes = sum(blob.size or 0 for blob in unread)
        is_fully_confirmed = usage_check_warning is None and len(unread) == len(eligible)

        candidates.append(
            WasteCandidate(
                bucket_name=bucket_name,
                eligible_object_count=len(eligible),
                eligible_size_bytes=size_bytes,
                oldest_object_age_days=oldest_age_days,
                estimated_savings_usd_month_min=_savings_usd_month(
                    size_bytes, settings.gcs_storage_price_usd_per_gb_month_nearline
                ),
                estimated_savings_usd_month_max=_savings_usd_month(
                    size_bytes, settings.gcs_storage_price_usd_per_gb_month_coldline
                ),
                usage_confirmed_object_count=len(unread) if usage_check_warning is None else 0,
                usage_confirmed_size_bytes=usage_confirmed_size_bytes
                if usage_check_warning is None
                else 0,
                confidence="usage_confirmed" if is_fully_confirmed else "config_based",
            )
        )

    return WasteCandidatesResponse(
        project_id=project_id,
        min_days_unused=min_days_unused,
        candidates=candidates,
        savings_disclaimer=_SAVINGS_DISCLAIMER,
        usage_check_warning=usage_check_warning,
    )


def _read_object_keys_or_warning(
    logging_client: cloud_logging.Client, project_id: str
) -> tuple[set[tuple[str, str]], str | None]:
    """Nunca propaga erro pra get_waste_candidates — a checagem 6.2 é
    best-effort, degradando pra "config_based" em vez de derrubar a
    requisição inteira (falta de acesso a Cloud Logging não deveria
    esconder o resultado, já útil, da checagem 6.1)."""
    try:
        keys = repository.list_read_object_keys(
            logging_client, project_id, _USAGE_CHECK_LOOKBACK_DAYS
        )
    except LoggingAccessDeniedError:
        return set(), _USAGE_CHECK_FORBIDDEN_WARNING
    if not keys:
        return set(), _USAGE_CHECK_EMPTY_WARNING.format(days=_USAGE_CHECK_LOOKBACK_DAYS)
    return keys, None


def _has_lifecycle_rule(bucket: storage.Bucket) -> bool:
    return len(list(bucket.lifecycle_rules)) > 0


def _savings_usd_month(size_bytes: int, target_price_per_gb: float) -> float:
    gb = size_bytes / (1024**3)
    price_diff = settings.gcs_storage_price_usd_per_gb_month_standard - target_price_per_gb
    return round(gb * price_diff, 4)
