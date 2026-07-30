"""Admin request and response contracts.

Kept apart from `schemas.py` so the public surface stays easy to read on its own.

Times cross this boundary as **naive Vegas wall clock**, in both directions. That is
what John types, what the source page says, and what the review form shows — so the
single conversion to UTC happens server-side in tested code, and neither the browser
nor the model is ever asked to reason about Pacific time.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import PriceTier, Vibe, Weekday
from .models import Event
from .timewindow import VEGAS_TZ

LOCAL_FORMAT = "%Y-%m-%dT%H:%M"


def to_local_string(moment: datetime) -> str:
    return moment.astimezone(VEGAS_TZ).strftime(LOCAL_FORMAT)


def _reject_aware(value: datetime) -> datetime:
    if value.tzinfo is not None:
        raise ValueError("Send a naive Vegas local time, with no offset or 'Z'.")
    return value


class RecurrenceIn(BaseModel):
    """Turns one event into a series of nights. Omitted means a single occurrence."""

    weekdays: list[Weekday] = Field(default_factory=list)
    until_local_date: date | None = None


class EventWriteIn(BaseModel):
    """The full event body, used for both create and replace."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    venue: str = Field(min_length=1, max_length=160)
    neighborhood: str = Field(min_length=1, max_length=80)
    address: str | None = Field(default=None, max_length=240)
    starts_at_local: datetime
    ends_at_local: datetime
    # The primary category — one value, because it drives the card's colours.
    vibe: Vibe
    # Any additional categories. The primary vibe is added server-side, so sending it
    # here is allowed but unnecessary.
    tags: list[Vibe] = Field(default_factory=list)
    # Set this only on an explicit signal ("dry", "sober", "alcohol-free", "no bar").
    # Absence of any mention of alcohol is not evidence.
    alcohol_free: bool = False
    price_tier: PriceTier
    price_note: str | None = Field(default=None, max_length=120)
    hook: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1)
    image_url: str | None = Field(default=None, max_length=500)
    video_url: str | None = Field(default=None, max_length=500)
    ticket_url: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    # Copy image_url into R2 on save so the card survives the venue's next redesign.
    mirror_image: bool = True
    # Only honoured on create; a series is generated once, then edited per night.
    recurrence: RecurrenceIn | None = None

    _no_tz = field_validator("starts_at_local", "ends_at_local")(_reject_aware)

    @model_validator(mode="after")
    def _check_ordering(self) -> EventWriteIn:
        if self.ends_at_local <= self.starts_at_local:
            raise ValueError("ends_at_local must be after starts_at_local.")
        return self


class TipWriteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue: str | None = Field(default=None, max_length=160)
    vibe: Vibe | None = None
    tip: str = Field(min_length=1)
    is_active: bool = True
    priority: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def _needs_a_target(self) -> TipWriteIn:
        if not self.venue and not self.vibe:
            raise ValueError("A tip needs a venue, a vibe, or both — otherwise it matches nothing.")
        return self


class AdminEventOut(BaseModel):
    """Everything about an event, including the fields the public API hides."""

    id: str
    name: str
    venue: str
    neighborhood: str
    address: str | None
    start_at: datetime
    end_at: datetime
    starts_at_local: str
    ends_at_local: str
    vibe: str
    tags: list[str]
    alcohol_free: bool
    price_tier: str
    price_note: str | None
    hook: str
    description: str
    image_url: str | None
    video_url: str | None
    ticket_url: str | None
    source_url: str | None
    is_active: bool
    is_sample: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_event(cls, event: Event) -> AdminEventOut:
        return cls(
            id=event.id,
            name=event.name,
            venue=event.venue,
            neighborhood=event.neighborhood,
            address=event.address,
            start_at=event.start_at,
            end_at=event.end_at,
            starts_at_local=to_local_string(event.start_at),
            ends_at_local=to_local_string(event.end_at),
            vibe=event.vibe,
            tags=event.tag_values,
            alcohol_free=event.alcohol_free,
            price_tier=event.price_tier,
            price_note=event.price_note,
            hook=event.hook,
            description=event.description,
            image_url=event.image_url,
            video_url=event.video_url,
            ticket_url=event.ticket_url,
            source_url=event.source_url,
            is_active=event.is_active,
            is_sample=event.is_sample,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )


class AdminTipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    venue: str | None
    vibe: str | None
    tip: str
    is_active: bool
    priority: int
    created_at: datetime


class DuplicateWarning(BaseModel):
    """Returned with a 409 so the UI can show what it collided with."""

    attempted_start_local: str
    existing: list[AdminEventOut]


class EventWriteOut(BaseModel):
    created: list[AdminEventOut]
    image_mirrored: bool
    # Populated when saving succeeded but the image copy did not — the event is live
    # either way, using its generated poster.
    image_warning: str | None = None


class ExtractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(default=None, max_length=2000)
    text: str | None = Field(default=None, max_length=200_000)

    @model_validator(mode="after")
    def _exactly_one(self) -> ExtractIn:
        if bool(self.url) == bool(self.text):
            raise ValueError("Send either a url or pasted text, not both and not neither.")
        return self


class ExtractedDraft(BaseModel):
    """The draft, shaped so the review form can load it without transformation."""

    name: str
    venue: str
    neighborhood: str
    starts_at_local: str
    ends_at_local: str
    vibe: str
    price_tier: str
    price_note: str | None
    hook: str
    description: str
    ticket_url: str | None
    image_url: str | None
    source_url: str | None


class ExtractRecurrenceOut(BaseModel):
    repeats: bool
    weekdays: list[str]
    until_local_date: str | None


class ExtractOut(BaseModel):
    found_event: bool
    draft: ExtractedDraft | None
    recurrence: ExtractRecurrenceOut
    uncertain_fields: list[str]
    notes: str
