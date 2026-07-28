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
