"""Request and response contracts.

Every request body is a Pydantic model and every client-supplied filter is an enum,
so no freeform string from the browser reaches a query.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import PriceTier, Vibe

_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    venue: str
    neighborhood: str
    start_at: datetime
    end_at: datetime
    vibe: Vibe
    price_tier: PriceTier
    price_note: str | None = None
    hook: str
    description: str
    image_url: str | None = None
    video_url: str | None = None
    ticket_url: str | None = None
    is_sample: bool = False
    # Resolved per-event from the tips table; null when nothing matches.
    insider_tip: str | None = None


class EventListOut(BaseModel):
    items: list[EventOut]
    total: int
    limit: int
    offset: int
    has_more: bool
    # True while the catalog still contains seeded placeholder events.
    sample_data: bool


class ShareCreateIn(BaseModel):
    # The 100 ceiling is an anti-abuse bound on payload size; the real product cap
    # (MAX_SHARE_EVENTS) is enforced in the router so it stays configurable.
    event_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("event_ids")
    @classmethod
    def _validate_ids(cls, raw: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for value in raw:
            candidate = value.strip().lower()
            if not _ID_PATTERN.match(candidate):
                raise ValueError("event_ids must be 32-character hex ids")
            if candidate not in seen:
                seen.add(candidate)
                cleaned.append(candidate)
        return cleaned


class ShareCreateOut(BaseModel):
    token: str
    expires_at: datetime
    # Relative on purpose: the client owns the public origin, the API does not.
    path: str


class ShareOut(BaseModel):
    token: str
    expires_at: datetime
    events: list[EventOut]
