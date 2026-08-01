"""Expanding a recurring event into one row per occurrence.

Vegas runs on residencies and weekly club nights, but the listing, the date filters and
the share snapshots all assume concrete rows. So a residency is stored as what it
actually is — a series of individual nights — and this module generates them.

Occurrences are built in Vegas wall-clock time and converted per-occurrence, so a
weekly 10pm night stays at 10pm on both sides of a DST change rather than drifting to
9pm or 11pm for half the season.

Two patterns, because Vegas needs both and one cannot express the other:

* **Every N weeks** on given weekdays. N=1 is the ordinary weekly night; N=2 is the
  fortnightly one that used to be flattened into a weekly and produced twice as many
  nights as existed.
* **The nth weekday of the month** — first Friday, last Thursday. This is *not* an
  interval. Months are not a whole number of weeks, so "every 4 weeks" yields thirteen
  occurrences a year and slides earlier through the month until a first-Friday event is
  landing in the previous month. First Friday in the Arts District is exactly the kind
  of locals event this catalog exists for, so it gets its own rule rather than an
  approximation.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from .timewindow import vegas_local_to_utc

# "The last one in the month", whichever week that falls in. Its own value because a
# month has four or five of a given weekday depending on the month, so "the 5th" is not
# a synonym and would silently skip the short months.
LAST_WEEK_OF_MONTH = -1


def _nth_weekday(year: int, month: int, weekday: int, position: int) -> date | None:
    """The `position`-th `weekday` of a month, or None if that month has no such date.

    `position` is 1-based, or LAST_WEEK_OF_MONTH for the last one. Returning None rather
    than clamping matters: a month with four Fridays genuinely has no fifth Friday, and
    inventing one by falling back to the fourth would put an event on a date the venue
    never announced.
    """
    days_in_month = calendar.monthrange(year, month)[1]
    matching = [
        day
        for day in range(1, days_in_month + 1)
        if date(year, month, day).weekday() == weekday
    ]
    if not matching:  # unreachable for a real month, but not worth assuming
        return None
    if position == LAST_WEEK_OF_MONTH:
        return date(year, month, matching[-1])
    if 1 <= position <= len(matching):
        return date(year, month, matching[position - 1])
    return None


def _month_after(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def expand_occurrences(
    *,
    first_start_local: datetime,
    duration: timedelta,
    weekdays: Sequence[int] = (),
    interval_weeks: int = 1,
    month_position: int | None = None,
    until_local: date | None = None,
    limit: int = 26,
) -> list[tuple[datetime, datetime]]:
    """Return (start_utc, end_utc) pairs for a recurring event, first night included.

    `weekdays` uses datetime.weekday() numbering (Monday is 0). An empty sequence means
    "the same weekday as the first occurrence", which is the common residency case.

    `interval_weeks` skips weeks: 1 is every week, 2 every other week. Counted from the
    week the first occurrence falls in, so the first night is always included and the
    rhythm is anchored to a date John actually chose rather than to the calendar.

    `month_position` switches to the monthly pattern — 1 for the first such weekday of
    each month, LAST_WEEK_OF_MONTH for the last. It ignores `interval_weeks`, which is a
    different way of describing when something happens rather than a modifier of it.

    `until_local` is inclusive. Without it, generation stops at `limit`, so a run with
    no stated end still produces a reviewable batch rather than an unbounded one.
    """
    if first_start_local.tzinfo is not None:
        raise ValueError("first_start_local must be naive Vegas local time.")
    if limit < 1:
        return []
    if duration <= timedelta(0):
        raise ValueError("duration must be positive.")
    if interval_weeks < 1:
        raise ValueError("interval_weeks must be at least 1.")
    if month_position is not None and not (
        month_position == LAST_WEEK_OF_MONTH or 1 <= month_position <= 5
    ):
        raise ValueError("month_position must be 1-5 or LAST_WEEK_OF_MONTH.")

    wanted = sorted(set(weekdays)) or [first_start_local.weekday()]
    if any(day < 0 or day > 6 for day in wanted):
        raise ValueError("weekdays must be 0-6, Monday first.")

    time_of_day = first_start_local.time()

    if month_position is not None:
        dates = _monthly_dates(
            first_start_local.date(), wanted, month_position, until_local, limit
        )
    else:
        dates = _weekly_dates(
            first_start_local.date(), wanted, interval_weeks, until_local, limit
        )

    return [
        (
            vegas_local_to_utc(datetime.combine(day, time_of_day)),
            vegas_local_to_utc(datetime.combine(day, time_of_day) + duration),
        )
        for day in dates
    ]


def _weekly_dates(
    first: date,
    weekdays: Sequence[int],
    interval_weeks: int,
    until: date | None,
    limit: int,
) -> list[date]:
    # Anchored to the Monday of the first occurrence's week, so "every other Friday"
    # counts from the Friday John entered rather than from an arbitrary epoch — two
    # people entering the same event a week apart would otherwise get opposite weeks.
    anchor_monday = first - timedelta(days=first.weekday())

    found: list[date] = []
    cursor = first
    # A hard walk ceiling: even fortnightly over a year is ~366 steps, and this keeps a
    # bad `until` from spinning.
    for _ in range(800):
        if len(found) >= limit:
            break
        if until is not None and cursor > until:
            break
        weeks_in = (cursor - anchor_monday).days // 7
        if cursor.weekday() in weekdays and weeks_in % interval_weeks == 0:
            found.append(cursor)
        cursor += timedelta(days=1)
    return found


def _monthly_dates(
    first: date,
    weekdays: Sequence[int],
    position: int,
    until: date | None,
    limit: int,
) -> list[date]:
    found: list[date] = []
    year, month = first.year, first.month

    # Twelve years of months is far past any `limit` worth generating, and bounds the
    # loop when `until` is absent.
    for _ in range(144):
        if len(found) >= limit:
            break

        for weekday in weekdays:
            day = _nth_weekday(year, month, weekday, position)
            # Skipped rather than clamped when the month has no such date, and skipped
            # before the first occurrence so the run starts where John said it does.
            if day is None or day < first:
                continue
            if until is not None and day > until:
                continue
            found.append(day)

        if until is not None and date(year, month, 1) > until:
            break
        year, month = _month_after(year, month)

    found.sort()
    return found[:limit]
