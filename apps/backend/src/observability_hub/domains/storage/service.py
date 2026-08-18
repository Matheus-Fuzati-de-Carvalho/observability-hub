from datetime import UTC, datetime

from google.cloud import storage

from observability_hub.core.config import settings
from observability_hub.domains.storage import repository
from observability_hub.domains.storage.schemas import (
    BucketsListResponse,
    BucketSummary,
    MinDaysUnused,
    WasteCandidate,
    WasteCandidatesResponse,
)

_SAVINGS_DISCLAIMER = (
    "Faixa calculada sobre bytes reais armazenados nos objetos elegíveis "
    "(STANDARD, mais antigos que o threshold), não sobre suposição de "
    "padrão de acesso. Mínimo assume migração pra NEARLINE (mais "
    "conservadora); máximo assume COLDLINE (mais agressiva). ARCHIVE fica "
    "de fora de propósito — custo de retrieval e duração mínima de 365 "
    "dias tornam a recomendação automática arriscada."
)

_NEVER_READ_LIMITATION = (
    "Este scanner não verifica se os objetos elegíveis foram efetivamente "
    'lidos ("objeto nunca lido") — isso exigiria Data Access audit logs '
    "do Cloud Storage habilitados, configuração separada da usada pelo "
    "BigQuery (ver docs/onboarding-cliente.md). A regra aqui é só idade + "
    "ausência de lifecycle rule configurada."
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
    client: storage.Client, project_id: str, min_days_unused: MinDaysUnused
) -> WasteCandidatesResponse:
    now = datetime.now(UTC)
    buckets = [
        bucket
        for bucket in repository.list_buckets(client, project_id)
        if not _has_lifecycle_rule(bucket)
    ]

    candidates = []
    for bucket in buckets:
        eligible = repository.get_eligible_waste_objects(
            client, project_id, bucket.name, int(min_days_unused), now
        )
        if not eligible:
            continue
        size_bytes = sum(blob.size or 0 for blob in eligible)
        oldest_age_days = max((now - (blob.custom_time or blob.updated)).days for blob in eligible)
        candidates.append(
            WasteCandidate(
                bucket_name=bucket.name,
                eligible_object_count=len(eligible),
                eligible_size_bytes=size_bytes,
                oldest_object_age_days=oldest_age_days,
                estimated_savings_usd_month_min=_savings_usd_month(
                    size_bytes, settings.gcs_storage_price_usd_per_gb_month_nearline
                ),
                estimated_savings_usd_month_max=_savings_usd_month(
                    size_bytes, settings.gcs_storage_price_usd_per_gb_month_coldline
                ),
            )
        )

    return WasteCandidatesResponse(
        project_id=project_id,
        min_days_unused=min_days_unused,
        candidates=candidates,
        savings_disclaimer=_SAVINGS_DISCLAIMER,
        limitation=_NEVER_READ_LIMITATION,
    )


def _has_lifecycle_rule(bucket: storage.Bucket) -> bool:
    return len(list(bucket.lifecycle_rules)) > 0


def _savings_usd_month(size_bytes: int, target_price_per_gb: float) -> float:
    gb = size_bytes / (1024**3)
    price_diff = settings.gcs_storage_price_usd_per_gb_month_standard - target_price_per_gb
    return round(gb * price_diff, 4)
