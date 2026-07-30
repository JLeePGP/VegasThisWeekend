"""Public event endpoints.

Results are always paginated — there is no endpoint that dumps the full catalog.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..enums import DateFilter, PriceTier, Vibe
from ..limiter import limiter
from ..models import Event, EventTag
from ..schemas import EventListOut, EventOut
from ..timewindow import now_utc, resolve_window
from ..tips import load_tip_buckets, match_tip

router = APIRouter(tags=["events"])
settings = get_settings()


def _serialise(row: Event, buckets) -> EventOut:
    payload = EventOut.model_validate(row)
    payload.insider_tip = match_tip(row, buckets)
    return payload


@router.get("/events", response_model=EventListOut)
@limiter.limit("100/minute")
def list_events(
    request: Request,
    date_filter: DateFilter = Query(DateFilter.WEEKEND, alias="date"),
    on: date | None = Query(None, description="A specific Vegas date (YYYY-MM-DD)."),
    vibe: list[Vibe] | None = Query(None, description="Repeatable; any match."),
    price: list[PriceTier] | None = Query(None, description="Repeatable; any match."),
    alcohol_free: bool = Query(
        False,
        description=(
            "Restrict to alcohol-free events. Composes with `vibe` using AND, not OR: "
            "vibe=nightlife&alcohol_free=true means sober nightlife, which is the whole "
            "reason this is not simply another vibe."
        ),
    ),
    limit: int = Query(20, ge=1, le=20),
    offset: int = Query(0, ge=0, le=5_000),
    db: Session = Depends(get_db),
) -> EventListOut:
    start_utc, end_utc = resolve_window(date_filter, on)

    conditions = [
        Event.is_active.is_(True),
        # Anything already over drops out of the stack regardless of the window.
        Event.end_at >= now_utc(),
    ]
    # The window applies to when an event starts; see timewindow for why.
    if start_utc is not None:
        conditions.append(Event.start_at >= start_utc)
    if end_utc is not None:
        conditions.append(Event.start_at < end_utc)
    if vibe:
        wanted = [v.value for v in vibe]
        # Primary column OR the extra-categories table, so an event tagged both fitness
        # and outdoors turns up under either. Testing the column too means an event with
        # no tag rows at all still appears under its own category — the tag table is
        # purely additive and cannot hide anything.
        conditions.append(
            or_(
                Event.vibe.in_(wanted),
                Event.id.in_(select(EventTag.event_id).where(EventTag.tag.in_(wanted))),
            )
        )
    if price:
        conditions.append(Event.price_tier.in_([p.value for p in price]))
    if alcohol_free:
        conditions.append(Event.alcohol_free.is_(True))

    total = db.scalar(select(func.count()).select_from(Event).where(*conditions)) or 0

    rows = db.scalars(
        select(Event)
        .where(*conditions)
        .order_by(Event.start_at.asc(), Event.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()

    buckets = load_tip_buckets(db)
    has_sample = bool(
        db.scalar(
            select(func.count())
            .select_from(Event)
            .where(Event.is_sample.is_(True), Event.is_active.is_(True))
        )
    )

    return EventListOut(
        items=[_serialise(row, buckets) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(rows) < total,
        sample_data=has_sample,
    )


@router.get("/events/{event_id}", response_model=EventOut)
@limiter.limit("100/minute")
def get_event(
    request: Request,
    event_id: str = Path(pattern=r"^[0-9a-f]{32}$"),
    db: Session = Depends(get_db),
) -> EventOut:
    row = db.get(Event, event_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Event not found.")
    return _serialise(row, load_tip_buckets(db))
