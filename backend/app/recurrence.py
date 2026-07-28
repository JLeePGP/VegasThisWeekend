"""Expanding a recurring event into one row per occurrence.

Vegas runs on residencies and weekly club nights, but the swipe stack, the date
filters and the share snapshots all assume concrete rows. So a residency is stored as
what it actually is — a series of individual nights — and this module generates them.

Occurrences are built in Vegas wall-clock time and converted per-occurrence, so a
weekly 10pm night stays at 10pm on both sides of a DST change rather than drifting to
9pm or 11pm for half the season.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from .timewindow import vegas_local_to_utc


def expand_occurrences(
    *,
    first_start_local: datetime,
    duration: timedelta,
    weekdays: Sequence[int] = (),
    until_local: date | None = None,
    limit: int = 26,
) -> list[tuple[datetime, datetime]]:
    """Return (start_utc, end_utc) pairs for a recurring event, first night included.

    `weekdays` uses datetime.weekday() numbering (Monday is 0). An empty sequence means
    "the same weekday as the first occurrence", which is the common residency case.
    `until_local` is inclusive. Without it, generation stops at `limit`, so a run with
    no stated end still produces a reviewable batch rather than an unbounded one.
    """
    if first_start_local.tzinfo is not None:
        raise ValueError("first_start_local must be naive Vegas local time.")
    if limit < 1:
        return []
    if duration <= timedelta(0):
        raise ValueError("duration must be positive.")

    wanted = sorted(set(weekdays)) or [first_start_local.weekday()]
    if any(day < 0 or day > 6 for day in wanted):
        raise ValueError("weekdays must be 0-6, Monday first.")

    occurrences: list[tuple[datetime, datetime]] = []
    cursor = first_start_local

    # A hard walk ceiling: even with one weekday a year of scanning is ~366 steps, and
    # this keeps a bad `until_local` from spinning.
    for _ in range(400):
        if len(occurrences) >= limit:
            break
        if until_local is not None and cursor.date() > until_local:
            break
        if cursor.weekday() in wanted and cursor >= first_start_local:
            occurrences.append(
                (vegas_local_to_utc(cursor), vegas_local_to_utc(cursor + duration))
            )
        cursor += timedelta(days=1)

    return occurrences
