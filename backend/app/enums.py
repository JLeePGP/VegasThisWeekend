"""Closed vocabularies for anything a client is allowed to send.

Filters are validated against these enums so no freeform string from the browser
ever reaches a query.
"""

from __future__ import annotations

from enum import Enum


class Vibe(str, Enum):
    """What kind of event this is.

    Note what is *not* here: "sober". Alcohol-free is an attribute that cuts across
    categories — a sober rave is nightlife AND alcohol-free — and vibe filters combine
    with OR, so a SOBER member would make "sober nightlife" the one query the filter
    could not express. It lives on `Event.alcohol_free` instead.
    """

    NIGHTLIFE = "nightlife"
    FOOD_DRINK = "food_drink"
    MUSIC = "music"
    SHOWS = "shows"
    SPORTS = "sports"
    OUTDOORS = "outdoors"
    FITNESS = "fitness"
    FAMILY = "family"
    ADULT = "adult"
    LOCAL = "local"


class Metric(str, Enum):
    """What the app counts.

    Deliberately a closed vocabulary: the recording endpoint is public, so anything
    outside this list is rejected rather than becoming a row someone can spam into the
    stats table.

    Metrics split into two kinds. The first group is per-event — the counter carries an
    event id and answers "which events land". The second is site-wide, where an event id
    is meaningless and is stored as null.

    Two members are gone with the swipe deck: `skip`, which was a swipe left, and
    `stack_exhausted`, which was running out of cards. Rows already recorded under those
    names are untouched and still read out of `stats.summary` — this list governs what
    the public endpoint will accept from now on, and neither can be produced any more.
    `list_end` is the honest successor to the second one; the first has no successor,
    because scrolling past a row is not a decision.
    """

    # Per-event
    SAVE = "save"
    DETAIL_OPEN = "detail_open"
    TIP_REVEAL = "tip_reveal"
    TICKET_CLICK = "ticket_click"
    WEBSITE_CLICK = "website_click"
    MAP_CLICK = "map_click"
    VIDEO_PLAY = "video_play"

    # Site-wide
    SHARE_CREATE = "share_create"
    SHARE_OPEN = "share_open"
    LIST_END = "list_end"
    SUBSCRIBE = "subscribe"
    SESSION_START = "session_start"
    # Launched from the home screen rather than a browser tab. Counted per session
    # rather than per install, because Safari reports installs to nobody — an install
    # counter would be Android-only and read as "nobody installs" when the audience is
    # mostly iPhone. Installed *usage* is also the better question: an install nobody
    # opens is worth nothing.
    STANDALONE_SESSION = "standalone_session"
    # Chromium's `appinstalled` event. Android and desktop Chrome only, by construction —
    # see the note above before reading anything into its size.
    APP_INSTALLED = "app_installed"

    @property
    def is_per_event(self) -> bool:
        return self in _PER_EVENT_METRICS


_PER_EVENT_METRICS = frozenset(
    {
        Metric.SAVE,
        Metric.DETAIL_OPEN,
        Metric.TIP_REVEAL,
        Metric.TICKET_CLICK,
        Metric.WEBSITE_CLICK,
        Metric.MAP_CLICK,
        Metric.VIDEO_PLAY,
    }
)

# Recorded before the swipe deck was removed on 1 Aug 2026. Not accepted by the public
# endpoint any more, but `stats.summary` still reports what was already counted.
LEGACY_METRICS = ("skip", "stack_exhausted")


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
