from pydantic import BaseModel


class BucketSummary(BaseModel):
    name: str
    location: str
    storage_class: str
    total_size_bytes: int
    object_count: int
    has_lifecycle_rule: bool


class BucketsListResponse(BaseModel):
    buckets: list[BucketSummary]
