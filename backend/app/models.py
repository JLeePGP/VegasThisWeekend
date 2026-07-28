"""ORM models.

Every timestamp is stored and returned as UTC. Vegas-local reasoning ("tonight",
"this weekend") happens in `timewindow.py`, never in the storage layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.types import JSON, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class UtcDateTime(TypeDecorator):
    """Timezone-aware datetimes that survive SQLite.

    Postgres stores the offset; SQLite silently drops it and hands back naive values,
    which would then be misread as local time. Normalising on the way in and out keeps
    both dialects behaving identically.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime rejected; attach a timezone before saving.")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    # Random ids, not sequential integers, so the catalog cannot be enumerated.
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)

    name: Mapped[str] = mapped_column(String(200))
    venue: Mapped[str] = mapped_column(String(160))
    neighborhood: Mapped[str] = mapped_column(String(80))

    start_at: Mapped[datetime] = mapped_column(UtcDateTime)
    end_at: Mapped[datetime] = mapped_column(UtcDateTime)

    vibe: Mapped[str] = mapped_column(String(32))
    price_tier: Mapped[str] = mapped_column(String(16))
    # Human-readable detail like "$25 advance / $35 door". Display only, never filtered on.
    price_note: Mapped[str | None] = mapped_column(String(120), nullable=True)

    hook: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)

    # Null image_url is expected: the client renders a generated poster instead.
    # Real events point at Cloudflare R2.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ticket_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Expired events are flagged inactive, never deleted.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # True for seeded placeholder data. Drives the "sample data" banner in the UI so
    # fabricated listings can never be mistaken for real ones.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_events_window", "is_active", "start_at", "end_at"),
        Index("ix_events_vibe", "vibe"),
    )


class InsiderTip(Base):
    """John-curated tips, matched to an event by venue or by vibe.

    Editable straight in the database — adding one never requires a redeploy.
    """

    __tablename__ = "insider_tips"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)

    # At least one of these is set. Venue matches beat vibe matches.
    venue: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    vibe: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    tip: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Higher wins when several tips match the same event.
    priority: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow)


class ShareList(Base):
    """An anonymous, read-only snapshot of saved event ids.

    Holds no user identity: a random token, a list of event ids, and an expiry.
    """

    __tablename__ = "share_lists"

    token: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    event_ids: Mapped[list[str]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
