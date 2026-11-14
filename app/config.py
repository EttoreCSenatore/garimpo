from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_ADMIN_TOKENS = {"", "change-me-to-a-secure-token", "changeme", "admin", "secret"}
MIN_ADMIN_TOKEN_LENGTH = 24


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    debug: bool = False
    # Bind to loopback by default; containers set HOST=0.0.0.0 explicitly.
    host: str = "127.0.0.1"
    port: int = 8000

    # Identify the bot honestly and give site owners a way to reach you.
    user_agent: str = "TivolliBot/1.0 (+https://github.com/EttoreCSenatore/tivolli-sports)"
    base_url: str = "https://www.tivolli.com.br"
    requests_per_second: float = 1.0
    jitter_min_ms: int = 500
    jitter_max_ms: int = 1500
    max_retries: int = 3

    database_url: str = "sqlite:///./tivolli.db"

    # Empty means the admin endpoints are disabled. In production a strong
    # token is mandatory (see validate_for_runtime).
    admin_token: str = ""

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Exact hostnames the image proxy may fetch from (no wildcards, no IPs).
    image_proxy_allowed_hosts: str = "estatico.tivollisports.com.br,www.tivolli.com.br"
    image_proxy_max_bytes: int = 5 * 1024 * 1024

    # Simple per-client sliding-window limits (requests per minute). 0 disables.
    chat_rate_limit_per_minute: int = 30
    image_rate_limit_per_minute: int = 240
    # Set when running behind a trusted reverse proxy so X-Forwarded-For is used.
    trust_proxy_headers: bool = False

    chat_max_message_length: int = 500
    chat_max_sessions: int = 5000

    splunk_hec_url: str = "https://localhost:8088/services/collector/event"
    splunk_hec_token: str = ""
    splunk_hec_verify_ssl: bool = True
    splunk_hec_batch_size: int = 50
    splunk_buffer_file: str = "events.jsonl"
    splunk_buffer_max_lines: int = 10000

    scheduler_enabled: bool = True
    full_refresh_interval_minutes: int = 360
    incremental_refresh_interval_minutes: int = 15
    incremental_top_n: int = 200

    disclaimer: bool = False

    cache_ttl_seconds: int = 60
    hot_product_cache_size: int = 500

    @property
    def robots_disallowed(self) -> list[str]:
        return ["/tivadm43", "/homologacao"]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip() and o.strip() != "*"]

    @property
    def image_host_list(self) -> list[str]:
        return [h.strip().lower() for h in self.image_proxy_allowed_hosts.split(",") if h.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_for_runtime(self) -> None:
        """Fail fast on unsafe production configuration."""
        if not self.is_production:
            return
        if self.admin_token in INSECURE_ADMIN_TOKENS or len(self.admin_token) < MIN_ADMIN_TOKEN_LENGTH:
            raise RuntimeError(
                f"ADMIN_TOKEN must be set to a random value of at least {MIN_ADMIN_TOKEN_LENGTH} "
                "characters when APP_ENV=production (e.g. `openssl rand -hex 32`)."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
