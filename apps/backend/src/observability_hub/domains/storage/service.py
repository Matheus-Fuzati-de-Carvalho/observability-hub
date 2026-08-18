from google.cloud import storage

from observability_hub.domains.storage import repository
from observability_hub.domains.storage.schemas import (
    BucketFreshnessResponse,
    BucketsListResponse,
    BucketSummary,
)

_EMPTY_BUCKET_WARNING = (
    "Bucket '{bucket_name}' sem objetos (ou sem objetos legíveis pela "
    "service account do Hub) — não é possível determinar a última "
    "modificação. Não confundir com 'sem atividade recente': um bucket "
    "genuinamente vazio também cai neste caso."
)


def list_buckets(client: storage.Client, project_id: str) -> BucketsListResponse:
    buckets = repository.list_buckets(client, project_id)
    sizes_and_counts = repository.get_buckets_sizes_and_counts(
        client, [bucket.name for bucket in buckets]
    )
    return BucketsListResponse(
        buckets=[
            BucketSummary(
                name=bucket.name,
                location=bucket.location or "",
                storage_class=bucket.storage_class or "",
                total_size_bytes=sizes_and_counts[bucket.name][0],
                object_count=sizes_and_counts[bucket.name][1],
                has_lifecycle_rule=len(list(bucket.lifecycle_rules)) > 0,
            )
            for bucket in buckets
        ]
    )


def get_bucket_freshness(client: storage.Client, bucket_name: str) -> BucketFreshnessResponse:
    last_modified = repository.get_bucket_last_modified(client, bucket_name)
    return BucketFreshnessResponse(
        bucket_name=bucket_name,
        last_modified=last_modified,
        warning=_EMPTY_BUCKET_WARNING.format(bucket_name=bucket_name)
        if last_modified is None
        else None,
    )
