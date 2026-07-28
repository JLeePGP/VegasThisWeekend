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
