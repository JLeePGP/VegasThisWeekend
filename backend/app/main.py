"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .limiter import limiter
from .routers import admin, events, share

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production and not settings.cors_origin_list:
        raise RuntimeError("CORS_ORIGINS must be set in production.")
    # Alembic owns the schema — `alembic upgrade head` runs on deploy (see Procfile).
    # The app deliberately does not create tables at boot: once real events exist, a
    # process that quietly reshapes the database on startup is a liability.
    yield


app = FastAPI(
    title="VegasThisWeekend API",
    version="1.0.0",
    lifespan=lifespan,
    # No public API surface documentation in production.
    docs_url=None if settings.is_production else "/docs",
    openapi_url=None if settings.is_production else "/openapi.json",
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # No cookies anywhere. The admin panel sends a bearer token in a header, which is
    # not a credential in the CORS sense, so this stays false.
    allow_credentials=False,
    # PUT and DELETE are for the admin routes; Authorization carries the admin token.
    # Without that header in the allowlist the browser strips it and every admin call
    # fails as unauthenticated.
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)

app.include_router(events.router)
app.include_router(share.router)
app.include_router(admin.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
