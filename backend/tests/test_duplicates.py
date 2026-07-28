"""Duplicate detection — a warning surface, never a block."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from app.duplicates import find_possible_duplicates, name_similarity, normalise
from app.models import Event
from app.timewindow import VEGAS_TZ

from .test_api import FAR_FUTURE, add_event

BASE = datetime.combine(FAR_FUTURE, time(22), tzinfo=VEGAS_TZ)


class TestNormalise:
    def test_strips_case_and_punctuation(self):
        assert normalise("Midnight Mass!") == "midnight mass"

    def test_collapses_whitespace(self):
        assert normalise("  Neon   Cathedral  ") == "neon cathedral"


class TestNameSimilarity:
    def test_identical_names_match(self):
        assert name_similarity("Midnight Mass", "Midnight Mass") == 1.0

    def test_added_subtitle_still_matches(self):
        assert name_similarity("Midnight Mass", "Midnight Mass: Opening Night") == 1.0

    def test_different_events_do_not_match(self):
        assert name_similarity("Latin Night", "Ladies Night") < 0.82

    def test_empty_name_scores_zero(self):
        assert name_similarity("", "Midnight Mass") == 0.0


class TestFindPossibleDuplicates:
    def test_same_venue_and_time_is_flagged(self, db):
        add_event(db, name="Midnight Mass", venue="Neon Cathedral", start=BASE)
        matches = find_possible_duplicates(
            db, name="Something Else", venue="Neon Cathedral", start_at=BASE
        )
        assert len(matches) == 1

    def test_venue_match_ignores_case_and_padding(self, db):
        add_event(db, venue="Neon Cathedral", start=BASE)
        matches = find_possible_duplicates(
            db, name="Whatever", venue="  neon cathedral ", start_at=BASE
        )
        assert len(matches) == 1

    def test_similar_name_at_a_different_venue_is_flagged(self, db):
        add_event(db, name="Midnight Mass", venue="Neon Cathedral", start=BASE)
        matches = find_possible_duplicates(
            db, name="Midnight Mass: Opening Night", venue="The Gilded Owl", start_at=BASE
        )
        assert len(matches) == 1

    def test_different_event_at_the_same_hour_is_not_flagged(self, db):
        """A hundred things start at 10pm in Vegas; time alone must not match."""
        add_event(db, name="Latin Night", venue="Neon Cathedral", start=BASE)
        matches = find_possible_duplicates(
            db, name="Ladies Night", venue="Little Foxes", start_at=BASE
        )
        assert matches == []

    def test_same_venue_on_a_different_night_is_not_flagged(self, db):
        add_event(db, venue="Neon Cathedral", start=BASE)
        matches = find_possible_duplicates(
            db, name="Whatever", venue="Neon Cathedral", start_at=BASE + timedelta(days=1)
        )
        assert matches == []

    def test_doors_versus_showtime_still_matches(self, db):
        """Two sources disagreeing by a couple of hours is the common real case."""
        add_event(db, venue="Neon Cathedral", start=BASE)
        matches = find_possible_duplicates(
            db, name="Whatever", venue="Neon Cathedral", start_at=BASE + timedelta(hours=2)
        )
        assert len(matches) == 1

    def test_excluded_id_is_skipped(self, db):
        """So editing an event does not flag it as a duplicate of itself."""
        event = add_event(db, venue="Neon Cathedral", start=BASE)
        matches = find_possible_duplicates(
            db, name=event.name, venue=event.venue, start_at=BASE, exclude_id=event.id
        )
        assert matches == []
