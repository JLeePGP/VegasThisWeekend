"""Public event endpoints.

Results are always paginated — there is no endpoint that dumps the full catalog.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from .. import cache
from ..config import get_settings
from ..db import get_db
from ..enums import DateFilter, PriceTier, Vibe
from ..limiter import limiter
from ..models import Event, EventTag
from ..schemas import EventListOut, EventOut
from ..timewindow import listing_date, now_utc, now_vegas, resolve_window
from ..tips import load_tip_buckets, match_tip

router = APIRouter(tags=["events"])
settings = get_settings()


# How long a shared cache may serve a listing without asking again.
#
# The catalog changes when John adds an event, which is a handful of times a week — not
# per second. A minute of staleness is invisible to a visitor and is the difference
# between every visitor reaching Postgres and roughly one request per distinct filter
# combination per minute doing so.
#
# `max-age=0` keeps browsers revalidating, so a person who adds a filter sees fresh data;
# `s-maxage` applies only to shared caches like Cloudflare. `stale-while-revalidate` lets
# the edge serve the old copy while it fetches a new one, so nobody waits on the origin.
EDGE_CACHE = "public, max-age=0, s-maxage=60, stale-while-revalidate=120"


def _allow_edge_cache(response: Response) -> None:
    """Mark a response cacheable by shared caches.

    Only ever applied to endpoints whose body is identical for every visitor. Nothing
    behind auth and nothing keyed to a person goes through here — a single mistake would
    mean one visitor's response served to another.

    `Vary: Origin` because CORS puts the requesting origin in the response headers, and
    an edge that ignored that could hand a response built for one origin to another.
    """
    response.headers["Cache-Control"] = EDGE_CACHE
    response.headers["Vary"] = "Origin"


def _lead_event_id(db: Session, conditions) -> str | None:
    """The event promoted to the top of the feed today, or None to leave order alone.

    The first card is the app's first impression, and a still photo is a weak one in a
    feed built to look like TikTok — so a card with video leads when there is one.

    Which one rotates by listing day rather than at random. Random would not survive
    contact with either of the two things around this endpoint: the 60-second shared edge
    cache means every visitor gets one stored copy anyway, and offset pagination against a
    reshuffling order would duplicate some cards and skip others on scroll. A value that
    changes once a day is stable within any page-through and still varies for someone who
    comes back tomorrow.

    Chosen from the same filtered set the listing itself uses, so the promoted event is
    always one that belongs in the window the visitor is looking at. Returns None when the
    window has no video at all, which is the ordinary case for a narrow filter.
    """
    ids = db.scalars(
        select(Event.id)
        .where(*conditions, Event.video_url.is_not(None), Event.video_url != "")
        # Ordered before the pick so the rotation is over a stable sequence; an unordered
        # set would let the database's row order change which event leads.
        .order_by(Event.start_at.asc(), Event.id.asc())
    ).all()
    if not ids:
        return None
    return ids[listing_date(now_vegas()).toordinal() % len(ids)]


def _serialise(row: Event, buckets) -> EventOut:
    payload = EventOut.model_validate(row)
    payload.insider_tip = match_tip(row, buckets)
    return payload


@router.get("/events", response_model=EventListOut)
@limiter.limit("100/minute")
def list_events(
    request: Request,
    response: Response,
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

    # Expressed in the ORDER BY rather than by moving a row after the fact: the promotion
    # has to be part of one total ordering, or page 2 would serve the promoted event a
    # second time and drop whatever it displaced.
    lead_id = _lead_event_id(db, conditions)
    ordering = [Event.start_at.asc(), Event.id.asc()]
    if lead_id is not None:
        ordering.insert(0, case((Event.id == lead_id, 0), else_=1))

    rows = db.scalars(
        select(Event).where(*conditions).order_by(*ordering).limit(limit).offset(offset)
    ).all()

    buckets = load_tip_buckets(db)

    # Cached: this decides whether a banner shows, and it was a COUNT over the whole
    # table on every single list request. It changes only when John edits an event.
    has_sample = cache.get_or_set(
        cache.SAMPLE_DATA,
        lambda: bool(
            db.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.is_sample.is_(True), Event.is_active.is_(True))
            )
        ),
    )

    payload = EventListOut(
        items=[_serialise(row, buckets) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(rows) < total,
        sample_data=has_sample,
    )
    _allow_edge_cache(response)
    return payload


@router.get("/events/{event_id}", response_model=EventOut)
@limiter.limit("100/minute")
def get_event(
    request: Request,
    response: Response,
    event_id: str = Path(pattern=r"^[0-9a-f]{32}$"),
    db: Session = Depends(get_db),
) -> EventOut:
    row = db.get(Event, event_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Event not found.")
    payload = _serialise(row, load_tip_buckets(db))
    _allow_edge_cache(response)
    return payload
