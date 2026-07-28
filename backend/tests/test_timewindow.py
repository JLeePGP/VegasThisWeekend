"""Vegas-local date maths — the trickiest logic in the backend."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.enums import DateFilter
from app.timewindow import (
    VEGAS_TZ,
    day_bounds,
    listing_date,
    resolve_window,
    weekend_friday,
)


def vegas(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=VEGAS_TZ)


def _real_elapsed(day: date) -> timedelta:
    """Wall-clock-independent length of a listing day.

    Subtracting two datetimes that share a tzinfo object gives wall-clock arithmetic and
    silently ignores DST, so the comparison has to happen in UTC — which is also what the
    query actually runs against.
    """
    start, end = day_bounds(day)
    return end.astimezone(timezone.utc) - start.astimezone(timezone.utc)


# 2026: Jul 27 is a Monday, Jul 31 a Friday, Aug 1 a Saturday, Aug 2 a Sunday.
MONDAY = vegas(2026, 7, 27, 20)
FRIDAY = vegas(2026, 7, 31, 20)
SUNDAY = vegas(2026, 8, 2, 20)


class TestListingDate:
    def test_evening_belongs_to_that_day(self):
        assert listing_date(vegas(2026, 7, 31, 22)) == date(2026, 7, 31)

    def test_after_midnight_still_belongs_to_the_night_before(self):
        assert listing_date(vegas(2026, 8, 1, 2)) == date(2026, 7, 31)

    def test_rollover_starts_the_new_day(self):
        assert listing_date(vegas(2026, 8, 1, 5)) == date(2026, 8, 1)

    def test_sunrise_hike_belongs_to_the_new_day(self):
        assert listing_date(vegas(2026, 8, 1, 6)) == date(2026, 8, 1)

    def test_resolved_in_vegas_time_not_utc(self):
        # 03:00 UTC on Aug 1 is 20:00 Vegas on Jul 31.
        assert listing_date(datetime(2026, 8, 1, 3, tzinfo=timezone.utc)) == date(2026, 7, 31)


class TestWeekendFriday:
    def test_midweek_points_at_the_coming_friday(self):
        assert weekend_friday(MONDAY) == date(2026, 7, 31)

    def test_friday_points_at_itself(self):
        assert weekend_friday(FRIDAY) == date(2026, 7, 31)

    def test_sunday_still_points_at_the_weekend_underway(self):
        assert weekend_friday(SUNDAY) == date(2026, 7, 31)

    def test_late_saturday_night_counts_as_friday_night(self):
        assert weekend_friday(vegas(2026, 8, 1, 2)) == date(2026, 7, 31)


class TestResolveWindow:
    def test_weekend_runs_friday_morning_to_monday_rollover(self):
        start, end = resolve_window(DateFilter.WEEKEND, reference=MONDAY)
        assert start == vegas(2026, 7, 31, 5)
        assert end == vegas(2026, 8, 3, 5)

    def test_thursday_night_is_not_part_of_the_weekend(self):
        """Regression: an event running Thu 22:00 to Fri 03:00 is a Thursday event."""
        start, _ = resolve_window(DateFilter.WEEKEND, reference=MONDAY)
        assert vegas(2026, 7, 30, 22) < start

    def test_friday_night_spilling_into_saturday_is_inside_the_weekend(self):
        start, end = resolve_window(DateFilter.WEEKEND, reference=MONDAY)
        assert start <= vegas(2026, 7, 31, 23) < end

    def test_sunday_night_is_the_last_thing_in_the_weekend(self):
        start, end = resolve_window(DateFilter.WEEKEND, reference=MONDAY)
        assert start <= vegas(2026, 8, 2, 21) < end

    def test_monday_night_is_past_the_weekend(self):
        _, end = resolve_window(DateFilter.WEEKEND, reference=MONDAY)
        assert vegas(2026, 8, 3, 20) >= end

    def test_today_covers_one_rollover_day(self):
        start, end = resolve_window(DateFilter.TODAY, reference=MONDAY)
        assert start == vegas(2026, 7, 27, 5)
        assert end == vegas(2026, 7, 28, 5)

    def test_today_after_midnight_is_still_last_nights_listing_day(self):
        start, end = resolve_window(DateFilter.TODAY, reference=vegas(2026, 7, 28, 1))
        assert start == vegas(2026, 7, 27, 5)
        assert end == vegas(2026, 7, 28, 5)

    def test_all_is_unbounded(self):
        assert resolve_window(DateFilter.ALL, reference=MONDAY) == (None, None)

    def test_explicit_date_overrides_the_filter(self):
        start, end = resolve_window(DateFilter.WEEKEND, on_date=date(2026, 8, 12), reference=MONDAY)
        assert (start, end) == day_bounds(date(2026, 8, 12))

    def test_windows_are_returned_in_utc(self):
        start, end = resolve_window(DateFilter.TODAY, reference=MONDAY)
        assert start.tzinfo == timezone.utc and end.tzinfo == timezone.utc

    def test_consecutive_days_abut_without_gap_or_overlap(self):
        _, first_end = day_bounds(date(2026, 7, 31))
        second_start, _ = day_bounds(date(2026, 8, 1))
        assert first_end == second_start

    def test_listing_day_containing_fall_back_is_twenty_five_hours(self):
        # DST ends at 02:00 on Sun 1 Nov 2026, which lands inside Saturday's listing day
        # (05:00 Sat to 05:00 Sun) — so Saturday is the long one, not Sunday.
        assert _real_elapsed(date(2026, 10, 31)) == timedelta(hours=25)

    def test_listing_day_containing_spring_forward_is_twenty_three_hours(self):
        # DST starts at 02:00 on Sun 8 Mar 2026, inside Saturday's listing day.
        assert _real_elapsed(date(2026, 3, 7)) == timedelta(hours=23)

    def test_ordinary_day_either_side_of_a_transition_is_unaffected(self):
        for day in (date(2026, 11, 1), date(2026, 3, 8)):
            assert _real_elapsed(day) == timedelta(hours=24)
