from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    user_agent: str = "TivolliBot/1.0 (+https://yourdomain.example; contact@example.com)"
    base_url: str = "https://www.tivolli.com.br"
    requests_per_second: float = 1.0
    jitter_min_ms: int = 500
    jitter_max_ms: int = 1500
    max_retries: int = 3

    database_url: str = "sqlite:///./tivolli.db"

    admin_token: str = "change-me-to-a-secure-token"

    splunk_hec_url: str = "https://localhost:8088/services/collector/event"
    splunk_hec_token: str = ""
    splunk_hec_verify_ssl: bool = False
    splunk_hec_batch_size: int = 50
    splunk_buffer_file: str = "events.jsonl"
    splunk_buffer_max_lines: int = 10000

    full_refresh_interval_minutes: int = 360
    incremental_refresh_interval_minutes: int = 15
    incremental_top_n: int = 200

    disclaimer: bool = False

    cache_ttl_seconds: int = 60
    hot_product_cache_size: int = 500

    @property
    def robots_disallowed(self) -> list[str]:
        return ["/tivadm43", "/homologacao"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
