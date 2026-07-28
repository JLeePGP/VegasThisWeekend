"""Application settings, read from environment variables (.env for local dev).

No secret ever has a real default here — production values live in Railway env vars.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    # Railway injects DATABASE_URL for the Postgres plugin. Local dev falls back to
    # SQLite so the backend runs with no external services installed.
    database_url: str = "sqlite:///./vegasthisweekend.db"

    # Comma-separated exact origins. Never a wildcard in production.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Admin panel + AI extraction ---
    admin_token: str = ""
    anthropic_api_key: str = ""
    # Extraction is structured field-pulling with a few judgment calls, not long-horizon
    # agentic work, so Sonnet tier is the right fit — roughly a third of Opus 5's cost at
    # this volume. Override per-deployment if a page type turns out to need more.
    anthropic_model: str = "claude-sonnet-5"
    eventbrite_api_key: str = ""

    # Cloudflare R2, via its S3-compatible API. Every field must be set before image
    # mirroring turns on; until then events keep their generated posters.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""

    # Ceiling on how many occurrences one recurring event may generate in a single go.
    max_series_occurrences: int = 26
    # Refuse to mirror anything larger; a hostile page can advertise a huge image.
    max_image_bytes: int = 10_000_000

    share_ttl_days: int = 30
    max_share_events: int = 20
    page_size: int = 20

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise Railway's `postgres://` scheme onto the psycopg 3 driver."""
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def admin_enabled(self) -> bool:
        """Without a token the admin routes refuse every request rather than run open."""
        return bool(self.admin_token)

    @property
    def extraction_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def r2_enabled(self) -> bool:
        return all(
            (
                self.r2_account_id,
                self.r2_access_key_id,
                self.r2_secret_access_key,
                self.r2_bucket,
                self.r2_public_base_url,
            )
        )

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
