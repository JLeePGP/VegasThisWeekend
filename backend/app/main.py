"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .db import Base, engine
from .limiter import limiter
from .routers import events, share

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production and not settings.cors_origin_list:
        raise RuntimeError("CORS_ORIGINS must be set in production.")
    # The v1 schema has no migration history yet, so create_all is enough. Alembic
    # takes over when the admin panel starts changing tables in flight.
    Base.metadata.create_all(bind=engine)
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
    # No cookies and no browser-side auth, so credentialed requests are never needed.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    max_age=600,
)

app.include_router(events.router)
app.include_router(share.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
