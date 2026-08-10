from pydantic_settings import BaseSettings, SettingsConfigDict

# Regiões conhecidas do BigQuery consultadas em paralelo para descobrir
# automaticamente onde um projeto tem datasets (ver docs/specs/catalog.md).
BQ_REGIONS = [
    "US",
    "EU",
    "us-central1",
    "us-east1",
    "us-east4",
    "us-west1",
    "us-west2",
    "us-west3",
    "us-west4",
    "northamerica-northeast1",
    "southamerica-east1",
    "europe-west1",
    "europe-west2",
    "europe-west3",
    "europe-west4",
    "europe-west6",
    "europe-north1",
    "asia-east1",
    "asia-east2",
    "asia-northeast1",
    "asia-northeast2",
    "asia-northeast3",
    "asia-south1",
    "asia-southeast1",
    "asia-southeast2",
    "australia-southeast1",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OBSERVABILITY_HUB_")

    log_level: str = "INFO"
    region_discovery_max_workers: int = 8


settings = Settings()
