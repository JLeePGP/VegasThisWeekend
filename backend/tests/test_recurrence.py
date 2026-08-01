"""Series expansion — the thing that turns a residency into rows."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.recurrence import expand_occurrences
from app.timewindow import VEGAS_TZ

# 2026: Aug 7 is a Friday, Aug 8 a Saturday.
FRIDAY_NIGHT = datetime(2026, 8, 7, 22, 0)
THREE_HOURS = timedelta(hours=3)


def local(occurrence: datetime) -> datetime:
    return occurrence.astimezone(VEGAS_TZ)


class TestExpansion:
    def test_single_weekday_run(self):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT,
            duration=THREE_HOURS,
            weekdays=[4],
            until_local=date(2026, 8, 28),
        )
        assert [local(start).date().isoformat() for start, _ in occurrences] == [
            "2026-08-07",
            "2026-08-14",
            "2026-08-21",
            "2026-08-28",
        ]

    def test_until_date_is_inclusive(self):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT,
            duration=THREE_HOURS,
            weekdays=[4],
            until_local=date(2026, 8, 7),
        )
        assert len(occurrences) == 1

    def test_empty_weekdays_uses_the_first_occurrence_weekday(self):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT,
            duration=THREE_HOURS,
            until_local=date(2026, 8, 21),
        )
        assert all(local(start).weekday() == 4 for start, _ in occurrences)
        assert len(occurrences) == 3

    def test_multiple_weekdays(self):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT,
            duration=THREE_HOURS,
            weekdays=[4, 5],  # Friday and Saturday
            until_local=date(2026, 8, 15),
        )
        assert [local(start).date().isoformat() for start, _ in occurrences] == [
            "2026-08-07",
            "2026-08-08",
            "2026-08-14",
            "2026-08-15",
        ]

    def test_no_end_date_stops_at_the_limit(self):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT,
            duration=THREE_HOURS,
            weekdays=[4],
            until_local=None,
            limit=5,
        )
        assert len(occurrences) == 5

    def test_first_occurrence_is_always_included(self):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT,
            duration=THREE_HOURS,
            weekdays=[4],
            until_local=date(2026, 8, 7),
        )
        assert local(occurrences[0][0]).hour == 22

    def test_duration_is_preserved_on_every_night(self):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT,
            duration=THREE_HOURS,
            weekdays=[4],
            until_local=date(2026, 8, 21),
        )
        assert all(end - start == THREE_HOURS for start, end in occurrences)

    def test_end_before_start_is_rejected(self):
        with pytest.raises(ValueError):
            expand_occurrences(
                first_start_local=FRIDAY_NIGHT,
                duration=timedelta(0),
                weekdays=[4],
                until_local=date(2026, 8, 21),
            )

    def test_aware_start_is_rejected(self):
        with pytest.raises(ValueError):
            expand_occurrences(
                first_start_local=FRIDAY_NIGHT.replace(tzinfo=VEGAS_TZ),
                duration=THREE_HOURS,
                weekdays=[4],
                until_local=date(2026, 8, 21),
            )


class TestDaylightSaving:
    def test_wall_clock_time_survives_the_dst_change(self):
        """A 10pm residency stays at 10pm in November, not 9pm."""
        occurrences = expand_occurrences(
            # Fri 30 Oct is PDT; Fri 6 Nov is PST (clocks change Sun 1 Nov).
            first_start_local=datetime(2026, 10, 30, 22, 0),
            duration=THREE_HOURS,
            weekdays=[4],
            until_local=date(2026, 11, 6),
        )
        assert [local(start).hour for start, _ in occurrences] == [22, 22]

    def test_utc_hour_shifts_by_one_across_the_change(self):
        """The other side of the same coin: same wall clock, different absolute time."""
        occurrences = expand_occurrences(
            first_start_local=datetime(2026, 10, 30, 22, 0),
            duration=THREE_HOURS,
            weekdays=[4],
            until_local=date(2026, 11, 6),
        )
        before, after = (start.hour for start, _ in occurrences)
        assert after == (before + 1) % 24


class TestEveryNWeeks:
    """The pattern that used to be unrepresentable. A page saying "every other Tuesday"
    produced every Tuesday — twice as many nights as existed, published as real events."""

    def dates(self, **kwargs):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT, duration=THREE_HOURS, **kwargs
        )
        return [local(start).date().isoformat() for start, _ in occurrences]

    def test_interval_of_one_is_the_old_weekly_behaviour(self):
        assert self.dates(weekdays=[4], interval_weeks=1, until_local=date(2026, 8, 28)) == [
            "2026-08-07",
            "2026-08-14",
            "2026-08-21",
            "2026-08-28",
        ]

    def test_fortnightly_skips_the_weeks_between(self):
        assert self.dates(weekdays=[4], interval_weeks=2, until_local=date(2026, 9, 30)) == [
            "2026-08-07",
            "2026-08-21",
            "2026-09-04",
            "2026-09-18",
        ]

    def test_every_third_week(self):
        assert self.dates(weekdays=[4], interval_weeks=3, until_local=date(2026, 10, 2)) == [
            "2026-08-07",
            "2026-08-28",
            "2026-09-18",
        ]

    def test_the_first_night_is_always_included(self):
        """The rhythm is anchored to the date John entered, not to the calendar — two
        people entering the same event a week apart must not get opposite weeks."""
        for interval in (1, 2, 3, 4):
            assert self.dates(weekdays=[4], interval_weeks=interval, limit=1) == ["2026-08-07"]

    def test_several_weekdays_in_the_same_active_week(self):
        """A Friday-and-Saturday run every other week keeps both nights together rather
        than alternating between them."""
        assert self.dates(
            weekdays=[4, 5], interval_weeks=2, until_local=date(2026, 9, 6)
        ) == ["2026-08-07", "2026-08-08", "2026-08-21", "2026-08-22", "2026-09-04", "2026-09-05"]

    def test_the_time_of_day_survives_the_gap(self):
        occurrences = expand_occurrences(
            first_start_local=FRIDAY_NIGHT,
            duration=THREE_HOURS,
            weekdays=[4],
            interval_weeks=2,
            until_local=date(2026, 11, 30),
        )
        # Crosses the 1 Nov DST change; 10pm must stay 10pm rather than drifting an hour.
        assert {local(start).strftime("%H:%M") for start, _ in occurrences} == {"22:00"}

    def test_an_interval_below_one_is_rejected(self):
        with pytest.raises(ValueError):
            expand_occurrences(
                first_start_local=FRIDAY_NIGHT, duration=THREE_HOURS, interval_weeks=0
            )


class TestNthWeekdayOfTheMonth:
    """First Friday is an Arts District institution, and it is not an interval: months
    are not a whole number of weeks, so "every 4 weeks" gives thirteen a year and slides
    steadily earlier until it lands in the previous month."""

    def dates(self, first, **kwargs):
        occurrences = expand_occurrences(
            first_start_local=first, duration=THREE_HOURS, **kwargs
        )
        return [local(start).date().isoformat() for start, _ in occurrences]

    def test_first_friday_of_each_month(self):
        assert self.dates(
            datetime(2026, 8, 7, 18, 0),
            weekdays=[4],
            month_position=1,
            until_local=date(2026, 12, 31),
        ) == ["2026-08-07", "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04"]

    def test_last_thursday_of_each_month(self):
        assert self.dates(
            datetime(2026, 8, 27, 19, 0),
            weekdays=[3],
            month_position=-1,
            until_local=date(2026, 11, 30),
        ) == ["2026-08-27", "2026-09-24", "2026-10-29", "2026-11-26"]

    def test_last_is_not_a_synonym_for_the_fifth(self):
        """A month has four or five of a given weekday. Treating "last" as "the 5th"
        would silently skip every four-Friday month."""
        last = self.dates(
            datetime(2026, 8, 28, 19, 0),
            weekdays=[4],
            month_position=-1,
            until_local=date(2026, 12, 31),
        )
        assert last == ["2026-08-28", "2026-09-25", "2026-10-30", "2026-11-27", "2026-12-25"]

    def test_a_month_without_a_fifth_friday_is_skipped_not_clamped(self):
        """Falling back to the fourth would put an event on a date nobody announced."""
        fifths = self.dates(
            datetime(2026, 1, 30, 19, 0),
            weekdays=[4],
            month_position=5,
            until_local=date(2026, 6, 30),
        )
        # In that range only January and May have five Fridays. February, March, April
        # and June have four, and each is skipped rather than falling back to the fourth.
        assert fifths == ["2026-01-30", "2026-05-29"]

    def test_it_does_not_start_before_the_first_night(self):
        """Entering the third Saturday of August must not backfill August's earlier
        Saturdays or any month before it."""
        assert self.dates(
            datetime(2026, 8, 15, 20, 0),
            weekdays=[5],
            month_position=3,
            until_local=date(2026, 10, 31),
        ) == ["2026-08-15", "2026-09-19", "2026-10-17"]

    def test_the_monthly_pattern_ignores_the_weekly_interval(self):
        """They are two ways of describing when something happens, not a modifier and a
        base — accepting both silently would make the result unpredictable."""
        monthly = dict(
            first=datetime(2026, 8, 7, 18, 0),
            weekdays=[4],
            month_position=1,
            until_local=date(2026, 11, 30),
        )
        assert self.dates(**monthly) == self.dates(**monthly, interval_weeks=3)

    def test_limit_still_bounds_an_open_ended_run(self):
        assert len(self.dates(
            datetime(2026, 8, 7, 18, 0), weekdays=[4], month_position=1, limit=4
        )) == 4

    def test_an_impossible_position_is_rejected(self):
        for position in (0, 6, -2):
            with pytest.raises(ValueError):
                expand_occurrences(
                    first_start_local=FRIDAY_NIGHT,
                    duration=THREE_HOURS,
                    month_position=position,
                )
