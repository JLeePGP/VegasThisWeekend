"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .limiter import limiter
from .proxy_guard import came_through_proxy
from .routers import admin, events, interactions, share, subscribers

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

# Paths that must stay reachable without going through Cloudflare. Railway's own
# healthcheck hits the container directly, so requiring the secret everywhere would make
# every deploy fail its healthcheck and roll back — with the logs showing a healthy app.
PROXY_EXEMPT_PATHS = {"/health"}


# Registered before the CORS middleware below, which means CORS ends up *outside* it:
# Starlette wraps the last-added middleware outermost. That ordering matters — a 403 from
# here still gets CORS headers, so a browser shows the real status instead of an opaque
# CORS failure that looks like an entirely different problem.
@app.middleware("http")
async def require_proxy(request: Request, call_next):
    """Refuse requests that did not come through Cloudflare, once that is switched on.

    Off by default and inert until both `PROXY_SHARED_SECRET` is set and
    `REQUIRE_PROXY_SECRET` is true — see proxy_guard.py for why enabling it is a
    deliberate second step rather than a consequence of setting the secret.
    """
    if (
        settings.require_proxy_secret
        and request.url.path not in PROXY_EXEMPT_PATHS
        and not came_through_proxy(request)
    ):
        # Deliberately says nothing about what is missing or expected. Someone probing
        # the raw origin learns only that it declined.
        return JSONResponse(status_code=403, content={"detail": "Forbidden."})
    return await call_next(request)


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
app.include_router(interactions.router)
app.include_router(subscribers.router)
app.include_router(admin.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
