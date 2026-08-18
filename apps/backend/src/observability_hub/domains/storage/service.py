from google.cloud import storage

from observability_hub.domains.storage import repository
from observability_hub.domains.storage.schemas import BucketsListResponse, BucketSummary


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
                time_created=bucket.time_created,
                updated=bucket.updated,
            )
            for bucket in buckets
        ]
    )
