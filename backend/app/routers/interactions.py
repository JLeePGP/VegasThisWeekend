"""The public endpoint that records interaction counts.

Open by necessity — it is called by every visitor's browser — so it is written on the
assumption that anything reaching it may be junk or deliberate noise:

* metrics are a closed enum, so an unknown name is a 422 rather than a new row
* event ids are shape-checked and must resolve to a real event
* a single request can carry at most MAX_ITEMS interactions
* the whole endpoint is rate limited

Nothing about the caller is stored. No session id, no IP, no user agent — only the
counters go to the database, which is what makes this a replacement for a third-party
analytics script rather than a first-party copy of one.
"""

from __future__ import annotations

import re
from collections import Counter

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..enums import Metric
from ..limiter import limiter
from ..models import Event
from ..stats import record

router = APIRouter(tags=["interactions"])

ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
MAX_ITEMS = 50


class InteractionIn(BaseModel):
    metric: Metric
    event_id: str | None = Field(default=None, max_length=32)


class InteractionBatchIn(BaseModel):
    items: list[InteractionIn] = Field(min_length=1, max_length=MAX_ITEMS)


class InteractionOut(BaseModel):
    recorded: int


@router.post(
    "/interactions", response_model=InteractionOut, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit("60/minute")
def record_interactions(
    request: Request,
    payload: InteractionBatchIn,
    db: Session = Depends(get_db),
) -> InteractionOut:
    wanted_ids = {
        item.event_id
        for item in payload.items
        if item.event_id and ID_PATTERN.match(item.event_id)
    }
    known_ids = (
        set(db.scalars(select(Event.id).where(Event.id.in_(wanted_ids))).all())
        if wanted_ids
        else set()
    )

    counts: Counter[tuple[Metric, str | None]] = Counter()
    for item in payload.items:
        if item.metric.is_per_event:
            # Silently dropped rather than 4xx: a stale tab can hold an event that has
            # since been removed, and failing the whole batch would lose the other
            # interactions in it for no benefit.
            if item.event_id in known_ids:
                counts[(item.metric, item.event_id)] += 1
        else:
            counts[(item.metric, None)] += 1

    return InteractionOut(recorded=record(db, counts))
