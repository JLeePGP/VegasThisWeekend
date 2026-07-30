"""ORM models.

Every timestamp is stored and returned as UTC. Vegas-local reasoning ("tonight",
"this weekend") happens in `timewindow.py`, never in the storage layer.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.types import JSON, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    # Kept alongside `address` rather than replaced by it. It is what every existing
    # event has, what the cards currently show, and what the filters would need
    # rewriting to lose — so `address` is additive and this becomes derived later,
    # once real addresses are populated and verified.
    neighborhood: Mapped[str] = mapped_column(String(80))
    # Street address. Null on every event that predates this column; the UI falls back
    # to venue + neighborhood, and a maps link needs no API key — just the text.
    address: Mapped[str | None] = mapped_column(String(240), nullable=True)

    start_at: Mapped[datetime] = mapped_column(UtcDateTime)
    end_at: Mapped[datetime] = mapped_column(UtcDateTime)

    # The primary category: drives the poster colours and the chip on the card. The
    # full set an event belongs to lives in `tags`, which always contains this value.
    vibe: Mapped[str] = mapped_column(String(32))

    # Alcohol-free. Deliberately a column and not a Vibe — see the note on the enum.
    # Only ever set from an explicit signal; "the page didn't mention alcohol" is not
    # evidence, and guessing optimistically sends someone in recovery to a bar.
    alcohol_free: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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

    tags: Mapped[list[EventTag]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        # selectin rather than lazy loading: the list endpoint serialises 20 events at
        # once, and a lazy relationship would make that 21 queries.
        lazy="selectin",
    )

    @property
    def tag_values(self) -> list[str]:
        """Every category this event belongs to, primary vibe first.

        `tags` holds only the *additional* categories, so the primary is prepended here
        rather than stored twice.
        """
        rest = sorted(tag.tag for tag in self.tags if tag.tag != self.vibe)
        return [self.vibe, *rest]

    __table_args__ = (
        Index("ix_events_window", "is_active", "start_at", "end_at"),
        Index("ix_events_vibe", "vibe"),
        Index("ix_events_alcohol_free", "alcohol_free"),
    )


class EventTag(Base):
    """Additional categories for an event, beyond its primary vibe.

    Additional *only* — the primary vibe is not duplicated here. Filtering therefore
    tests the vibe column OR this table, which is marginally more query but removes an
    invariant that could silently hide events: an earlier design stored the primary vibe
    here too and filtered on this table alone, which meant any event created without tag
    rows disappeared from its own category. Nothing enforced that at the database level,
    and the seed and test fixtures both got it wrong immediately.
    """

    __tablename__ = "event_tags"

    event_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)

    event: Mapped[Event] = relationship(back_populates="tags")


class ExtractionDraft(Base):
    """One queued URL, and whatever extraction made of it.

    Server-side rather than held in the browser, for two reasons that both come from
    the Batch API being asynchronous: a batch can take the best part of an hour, so the
    tab has to be closable; and John wanted to keep adding URLs to a queue that is
    already running, which means the queue is shared state, not component state.

    Nothing here writes to `events`. A draft is a proposal — approving it is a separate,
    deliberate call, and the review form is the last line of defence against a page that
    tried to talk the model into something.
    """

    __tablename__ = "extraction_drafts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)

    url: Mapped[str] = mapped_column(String(2000))
    # queued -> running -> ready | failed | approved | discarded
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)

    # Set once submitted, so results can be collected after a restart. Null for drafts
    # that were extracted synchronously.
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # The ExtractOut payload, stored as-is so the review form can load it without a
    # translation layer. Null until extraction returns.
    draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Populated on failure. Shown verbatim — "Instagram needs a login" is more useful
    # than "extraction failed".
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set when approved, so the queue can link to what it produced.
    event_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (Index("ix_extraction_drafts_created", "created_at"),)


class StatCounter(Base):
    """Aggregate interaction counts. One row per (day, metric, event).

    Counters, not a log. There is no row per interaction, no session id, no IP, no user
    agent and nothing that could be tied back to a person — which is both the point and
    the reason this can replace a third-party analytics script rather than sit alongside
    one. What it can answer that a cookieless pageview tool cannot is "which events are
    people actually saving", because the count is attached to the event.

    `day` is a plain Las Vegas calendar date, not the 5am listing day used for event
    windows. A listing day answers "which night does this event belong to"; this answers
    "when did people use the app", and a session at 2am is genuinely that morning's
    usage, not the previous evening's.

    Site-wide metrics store a null event_id. Postgres and SQLite both treat NULLs in a
    unique index as distinct, so the uniqueness is enforced with two partial indexes
    rather than one composite key.
    """

    __tablename__ = "stat_counters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)

    day: Mapped[date] = mapped_column(Date, nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_stat_counters_day_metric", "day", "metric"),
        Index("ix_stat_counters_event", "event_id"),
        # Two indexes rather than one: a single unique index over a nullable column
        # would not stop duplicate site-wide rows, because NULL != NULL.
        Index(
            "uq_stat_counters_event",
            "day",
            "metric",
            "event_id",
            unique=True,
            sqlite_where=text("event_id IS NOT NULL"),
            postgresql_where=text("event_id IS NOT NULL"),
        ),
        Index(
            "uq_stat_counters_sitewide",
            "day",
            "metric",
            unique=True,
            sqlite_where=text("event_id IS NULL"),
            postgresql_where=text("event_id IS NULL"),
        ),
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
