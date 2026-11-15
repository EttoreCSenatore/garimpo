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
    user_agent: str = "GarimpoBot/1.0 (+https://github.com/EttoreCSenatore/garimpo)"
    base_url: str = "https://www.tivolli.com.br"
    requests_per_second: float = 1.0
    jitter_min_ms: int = 500
    jitter_max_ms: int = 1500
    max_retries: int = 3

    database_url: str = "sqlite:///./garimpo.db"

    # Empty means the admin endpoints are disabled. In production a strong
    # token is mandatory (see validate_for_runtime).
    admin_token: str = ""

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Exact hostnames the image proxy may fetch from (no wildcards, no IPs).
    image_proxy_allowed_hosts: str = "www.tivolli.com.br"
    image_proxy_max_bytes: int = 5 * 1024 * 1024

    # Simple per-client sliding-window limits (requests per minute). 0 disables.
    chat_rate_limit_per_minute: int = 30
    image_rate_limit_per_minute: int = 240
    # Set when running behind a trusted reverse proxy so X-Forwarded-For is used.
    trust_proxy_headers: bool = False

    chat_max_message_length: int = 500
    chat_max_sessions: int = 5000


    scheduler_enabled: bool = True
    full_refresh_interval_minutes: int = 360
    incremental_refresh_interval_minutes: int = 15
    incremental_top_n: int = 200

    disclaimer: bool = False

    cache_ttl_seconds: int = 60

    @property
    def robots_disallowed(self) -> list[str]:
        # Mirrors the store's robots.txt (Magento) plus the paths blocked since the old platform.
        return [
            "/admin", "/app", "/downloader", "/errors", "/includes", "/lib", "/pkginfo", "/shell",
            "/var", "/checkout", "/onestepcheckout", "/customer", "/wishlist", "/sendfriend",
            "/review", "/index.php", "/catalogsearch", "/catalog/product_compare",
            "/catalog/category/view", "/catalog/product/view", "/cgi-bin", "/tivadm43", "/homologacao",
        ]

    @property
    def robots_disallowed_params(self) -> set[str]:
        """Query parameters robots.txt forbids on listings (sorting, view modes, filters, sessions)."""
        return {
            "product_list_order", "product_list_dir", "product_list_mode", "product_list_limit",
            "dir", "limit", "mode", "price", "manufacturer", "color", "tamanho", "sid",
        }

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
