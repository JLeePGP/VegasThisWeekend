"""Bearer-token auth for the admin routes.

The admin panel runs on John's machine but talks to the deployed API, so these routes
are reachable from the internet and the token is the only thing standing in front of
them. Two consequences shape this module: an unset token disables the routes entirely
rather than leaving them open, and the comparison is constant-time so a wrong token
cannot be discovered one character at a time.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

# auto_error=False so a missing header produces our 401 with a WWW-Authenticate hint
# rather than FastAPI's bare 403.
_bearer_scheme = HTTPBearer(auto_error=False, description="Admin token")

_UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    settings = get_settings()

    if not settings.admin_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API is not configured on this deployment.",
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers=_UNAUTHORIZED,
        )

    if not secrets.compare_digest(credentials.credentials, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers=_UNAUTHORIZED,
        )
