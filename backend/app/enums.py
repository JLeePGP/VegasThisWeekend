"""Closed vocabularies for anything a client is allowed to send.

Filters are validated against these enums so no freeform string from the browser
ever reaches a query.
"""

from __future__ import annotations

from enum import Enum


class Vibe(str, Enum):
    NIGHTLIFE = "nightlife"
    FOOD_DRINK = "food_drink"
    MUSIC = "music"
    SHOWS = "shows"
    SPORTS = "sports"
    OUTDOORS = "outdoors"
    FAMILY = "family"
    ADULT = "adult"
    LOCAL = "local"


class PriceTier(str, Enum):
    """Buckets, not live prices — v1 explicitly does not track real-time pricing."""

    FREE = "free"          # $0
    BUDGET = "budget"      # under $50
    MODERATE = "moderate"  # $50-150
    PREMIUM = "premium"    # $150+


class DateFilter(str, Enum):
    TODAY = "today"
    WEEKEND = "weekend"
    ALL = "all"


class Weekday(str, Enum):
    """Used only by recurrence detection, so a residency can say which nights it runs."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @property
    def index(self) -> int:
        """Matches datetime.weekday(): Monday is 0."""
        return list(Weekday).index(self)


class Neighborhood(str, Enum):
    """A closed vocabulary for extraction only.

    The database column stays a free string so manual entry can say anything, but
    letting the model invent labels produces "The Strip", "Las Vegas Strip" and
    "Strip" as three different neighbourhoods on three different cards.
    """

    STRIP = "The Strip"
    OFF_STRIP = "Off-Strip"
    DOWNTOWN = "Downtown"
    ARTS_DISTRICT = "Arts District"
    CHINATOWN = "Chinatown"
    SUMMERLIN = "Summerlin"
    HENDERSON = "Henderson"
    EAST_SIDE = "East Side"
    WEST_SIDE = "West Side"
    NORTH_LAS_VEGAS = "North Las Vegas"
    SOUTHWEST = "Southwest"
    RED_ROCK = "Red Rock"
    ELSEWHERE = "Elsewhere"
