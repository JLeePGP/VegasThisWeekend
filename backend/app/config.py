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

    # Phase 2 (admin panel + AI extraction). Declared now so deploy config is complete.
    admin_token: str = ""
    anthropic_api_key: str = ""
    eventbrite_api_key: str = ""

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
