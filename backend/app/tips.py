"""Matching curated insider tips onto events.

Tips are few (dozens), so they are loaded once per request and matched in memory
rather than joined per event.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import cache
from .models import Event, InsiderTip

# (venue+vibe, venue-only, vibe-only) — checked in that order, most specific first.
TipBuckets = tuple[dict[tuple[str, str], str], dict[str, str], dict[str, str]]


def _venue_key(venue: str) -> str:
    return venue.strip().lower()


def load_tip_buckets(db: Session) -> TipBuckets:
    """Cached: identical for every visitor, and it was costing a query per request.

    See cache.py for why this is in-process rather than shared. The admin write paths
    invalidate it, so an edit shows up immediately on the instance that handled it and
    within the TTL everywhere else.
    """
    return cache.get_or_set(cache.TIP_BUCKETS, lambda: _load_tip_buckets_uncached(db))


def _load_tip_buckets_uncached(db: Session) -> TipBuckets:
    tips = db.scalars(
        select(InsiderTip)
        .where(InsiderTip.is_active.is_(True))
        # Highest priority first, so the setdefault below keeps the best match.
        .order_by(InsiderTip.priority.desc(), InsiderTip.created_at.asc())
    ).all()

    both: dict[tuple[str, str], str] = {}
    venue_only: dict[str, str] = {}
    vibe_only: dict[str, str] = {}

    for tip in tips:
        if tip.venue and tip.vibe:
            both.setdefault((_venue_key(tip.venue), tip.vibe), tip.tip)
        elif tip.venue:
            venue_only.setdefault(_venue_key(tip.venue), tip.tip)
        elif tip.vibe:
            vibe_only.setdefault(tip.vibe, tip.tip)

    return both, venue_only, vibe_only


def match_tip(event: Event, buckets: TipBuckets) -> str | None:
    both, venue_only, vibe_only = buckets
    venue = _venue_key(event.venue)
    return both.get((venue, event.vibe)) or venue_only.get(venue) or vibe_only.get(event.vibe)
