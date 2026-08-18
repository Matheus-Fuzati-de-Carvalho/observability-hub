from datetime import datetime

from pydantic import BaseModel


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
