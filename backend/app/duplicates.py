"""Warning about events that look like ones already in the catalog.

At 30-50 events a week pulled from several sources, adding the same night twice is a
matter of when rather than whether. This never blocks a save — it surfaces candidates
so John can decide, because two genuinely different events can share a venue and a
start time (two rooms, two stages).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Event

# Same venue within this window is worth a second look; a doors-vs-showtime
# discrepancy between two sources is routinely a couple of hours.
MATCH_WINDOW = timedelta(hours=6)

# Tuned so "Midnight Mass" and "Midnight Mass: Opening Night" match, while
# "Latin Night" and "Ladies Night" do not.
NAME_SIMILARITY_THRESHOLD = 0.82

_NOISE = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    return _SPACES.sub(" ", _NOISE.sub(" ", text.casefold())).strip()


def name_similarity(left: str, right: str) -> float:
    """Token-overlap similarity, so word order and added subtitles do not defeat it."""
    left_tokens = set(normalise(left).split())
    right_tokens = set(normalise(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    # Compare against the shorter title: "Midnight Mass" is fully contained in
    # "Midnight Mass Opening Night", and that should read as a strong match.
    return overlap / min(len(left_tokens), len(right_tokens))


def find_possible_duplicates(
    db: Session,
    *,
    name: str,
    venue: str,
    start_at: datetime,
    exclude_id: str | None = None,
) -> list[Event]:
    """Existing events that plausibly describe the same night.

    A candidate matches if it starts near the same time AND either shares the venue or
    has a near-identical name. Time proximity alone is far too broad in a city where
    a hundred things start at 10pm.
    """
    candidates = db.scalars(
        select(Event).where(
            Event.start_at >= start_at - MATCH_WINDOW,
            Event.start_at <= start_at + MATCH_WINDOW,
        )
    ).all()

    target_venue = normalise(venue)
    matches = []
    for candidate in candidates:
        if exclude_id is not None and candidate.id == exclude_id:
            continue
        same_venue = normalise(candidate.venue) == target_venue
        similar_name = name_similarity(candidate.name, name) >= NAME_SIMILARITY_THRESHOLD
        if same_venue or similar_name:
            matches.append(candidate)

    return sorted(matches, key=lambda event: event.start_at)
