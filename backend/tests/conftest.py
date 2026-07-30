"""Test fixtures.

The DATABASE_URL override has to happen before any app module is imported, because
`app.db` builds its engine at import time from the cached settings.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP_DIR = Path(tempfile.mkdtemp(prefix="vtw-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["ENVIRONMENT"] = "test"

ADMIN_TOKEN = "test-admin-token"
os.environ["ADMIN_TOKEN"] = ADMIN_TOKEN

# Forced empty, and deliberately not `setdefault`: a real key in the developer's
# environment or .env would otherwise let a test make a live, billable API call.
# Extraction tests patch the call site instead.
os.environ["ANTHROPIC_API_KEY"] = ""

# Same reasoning for R2 — no test should ever reach the network.
for _r2_var in (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "R2_PUBLIC_BASE_URL",
):
    os.environ[_r2_var] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Event,
    EventTag,
    ExtractionDraft,
    InsiderTip,
    ShareList,
    StatCounter,
)

# Rate limits are asserted separately; leaving them on would make unrelated tests flaky.
limiter.enabled = False


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        # EventTag before Event: SQLite does not enforce foreign keys unless explicitly
        # switched on, so the ON DELETE CASCADE cannot be relied on to clear the child
        # rows here even though it does in Postgres.
        for model in (EventTag, StatCounter, ExtractionDraft, Event, InsiderTip, ShareList):
            session.execute(delete(model))
        session.commit()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_client():
    """A client that carries the admin bearer token on every request."""
    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}"})
        yield test_client
