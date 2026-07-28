"""Vegas-local date reasoning.

Two decisions drive everything here.

1. "Tonight" means tonight *in Las Vegas*, not in the visitor's timezone. A tourist
   planning from New York at 1am Eastern is still asking about Vegas Thursday, so every
   window is computed in America/Los_Angeles and converted to UTC only for querying.

2. A night belongs to the day it started. A party running Friday 10pm to Saturday 3am is
   a Friday night, and a Thursday 10pm party is *not* part of the weekend just because it
   spills past midnight. So the day boundary sits at 5am rather than midnight, and an
   event is filed under the day its start time falls into.

The second rule means filtering happens on `start_at`. Genuinely multi-day events (a
three-day festival) should be entered as one row per day, which is also what makes sense
on a swipe card — you swipe on "Saturday of the festival", not the festival.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .enums import DateFilter

VEGAS_TZ = ZoneInfo("America/Los_Angeles")

# Where one listing day ends and the next begins. Late enough that a 3am club close still
# counts as the night before, early enough that a 6am sunrise hike counts as the new day.
# 05:00 is also safe across DST: unlike 01:00 it never occurs twice, and unlike 02:00 it
# never fails to occur at all.
DAY_ROLLOVER = time(5, 0)

# Python's weekday(): Monday is 0, Sunday is 6.
_FRIDAY = 4
_SUNDAY = 6


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_vegas() -> datetime:
    return datetime.now(VEGAS_TZ)


def listing_date(moment: datetime) -> date:
    """The day an event at this moment is filed under, per the 5am rollover."""
    local = moment.astimezone(VEGAS_TZ)
    if local.time() < DAY_ROLLOVER:
        return local.date() - timedelta(days=1)
    return local.date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Vegas-local [start, end) covering one listing day. End is exclusive.

    Both values carry the same tzinfo, so subtracting them gives wall-clock arithmetic
    that ignores DST. Convert to UTC first if you need real elapsed time.
    """
    start = datetime.combine(day, DAY_ROLLOVER, tzinfo=VEGAS_TZ)
    end = datetime.combine(day + timedelta(days=1), DAY_ROLLOVER, tzinfo=VEGAS_TZ)
    return start, end


def weekend_friday(reference: datetime | None = None) -> date:
    """The Friday of the weekend a user means by 'this weekend' right now.

    Once Friday has begun, 'this weekend' is the one already underway rather than the
    one seven days out.
    """
    today = listing_date(reference or now_utc())
    weekday = today.weekday()
    if weekday >= _FRIDAY:
        return today - timedelta(days=weekday - _FRIDAY)
    return today + timedelta(days=_FRIDAY - weekday)


def resolve_window(
    date_filter: DateFilter,
    on_date: date | None = None,
    reference: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """UTC bounds to apply to an event's start time, as [start, end).

    `None` on either side means unbounded. An explicit `on_date` always wins over
    `date_filter`. Callers are still responsible for excluding events that have already
    finished — that is a separate check against `end_at`, not part of the window.
    """
    if on_date is not None:
        start_local, end_local = day_bounds(on_date)

    elif date_filter is DateFilter.TODAY:
        start_local, end_local = day_bounds(listing_date(reference or now_utc()))

    elif date_filter is DateFilter.WEEKEND:
        friday = weekend_friday(reference)
        start_local, _ = day_bounds(friday)
        _, end_local = day_bounds(friday + timedelta(days=_SUNDAY - _FRIDAY))

    else:  # DateFilter.ALL — anything still to come, however far out.
        return None, None

    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
