"""Admin endpoints: event inventory, curated tips, and AI extraction.

Every route sits behind a bearer token. The panel itself runs on John's machine, but
these routes are served from the deployed API, so the token — not network location —
is what protects them.

Saving is deliberately a two-step conversation. Extraction returns a draft and writes
nothing; a create that collides with an existing event returns 409 with what it hit,
and only saves when explicitly forced. Neither the model nor a mis-click can put an
event in front of users on its own.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..config import get_settings
from ..db import get_db
from .. import cache
from ..bulk_extraction import (
    BulkExtractionError,
    collect as collect_batches,
    parse_urls,
    submit as submit_batch,
)
from ..client_ip import client_ip, resolve as resolve_client_sources
from ..duplicates import find_possible_duplicates
from ..extraction import ExtractionError, extract_event, parse_local
from ..images import ImageMirrorError, mirror_bytes_to_r2, mirror_to_r2
from ..limiter import limiter
from ..video_sources import (
    VideoResolveError,
    download_video_page,
    is_resolvable_video_page,
)
from ..models import Event, EventTag, ExtractionDraft, InsiderTip
from ..proxy_guard import secret_status
from ..recurrence import expand_occurrences
from ..stats import summary
from ..schemas_admin import (
    AdminEventOut,
    AdminTipOut,
    DuplicateWarning,
    EventWriteIn,
    EventUpdateOut,
    EventWriteOut,
    ExtractedDraft,
    ExtractIn,
    ExtractOut,
    ExtractRecurrenceOut,
    TipWriteIn,
    to_local_string,
)
from ..timewindow import now_utc, vegas_local_to_utc

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
settings = get_settings()

ID_PATTERN = r"^[0-9a-f]{32}$"

# Applied when a source gives a start time but no end.
DEFAULT_DURATION = timedelta(hours=3)


# ------------------------------------------------------------------ extraction


def build_extract_out(result, *, source_url: str | None) -> ExtractOut:
    """Turn a validated ExtractionResult into the payload the review form loads.

    Shared by the single-URL endpoint and the bulk batch collector. One implementation
    on purpose: the batch path validates the model's JSON by hand rather than through
    `messages.parse`, and two copies of this mapping would drift the moment a field was
    added — which is exactly what just happened with address, tags and alcohol_free.
    """
    recurrence = ExtractRecurrenceOut(
        repeats=result.recurrence.repeats,
        weekdays=[day.value for day in result.recurrence.weekdays],
        until_local_date=result.recurrence.until_local_date,
    )

    if not result.found_event or result.event is None:
        return ExtractOut(
            found_event=False,
            draft=None,
            recurrence=recurrence,
            uncertain_fields=result.uncertain_fields,
            notes=result.notes,
        )

    event = result.event
    # Validate the model's times here rather than at save: a malformed date should
    # surface on the screen John is already looking at.
    start_local = parse_local(event.starts_at_local, field="starts_at_local")
    if event.ends_at_local:
        end_local = parse_local(event.ends_at_local, field="ends_at_local")
    else:
        # Most listings give a start and no end. Three hours is a defensible default the
        # reviewer can correct, and it keeps the event from having a zero-length window.
        end_local = start_local + DEFAULT_DURATION

    return ExtractOut(
        found_event=True,
        draft=ExtractedDraft(
            name=event.name,
            venue=event.venue,
            neighborhood=event.neighborhood.value,
            address=event.address,
            starts_at_local=start_local.strftime("%Y-%m-%dT%H:%M"),
            ends_at_local=end_local.strftime("%Y-%m-%dT%H:%M"),
            vibe=event.vibe.value,
            # The model is told not to repeat the primary vibe here, but it is a model,
            # so the guarantee is enforced rather than trusted.
            tags=[tag.value for tag in event.tags if tag != event.vibe],
            alcohol_free=event.alcohol_free,
            price_tier=event.price_tier.value,
            price_note=event.price_note,
            hook=event.hook,
            description=event.description,
            ticket_url=event.ticket_url,
            image_url=event.image_url,
            source_url=source_url,
        ),
        recurrence=recurrence,
        uncertain_fields=result.uncertain_fields,
        notes=result.notes,
    )


@router.post("/extract", response_model=ExtractOut)
@limiter.limit("10/minute")
def extract(request: Request, payload: ExtractIn) -> ExtractOut:
    """Read a URL (or pasted text) and return a draft. Writes nothing."""
    try:
        result = extract_event(url=payload.url, text=payload.text)
    except ExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return build_extract_out(result, source_url=payload.url)


# ------------------------------------------------------------------ events


@router.get("/events", response_model=list[AdminEventOut])
@limiter.limit("20/minute")
def list_events(
    request: Request,
    q: str | None = Query(None, max_length=120, description="Match on name or venue."),
    include_inactive: bool = Query(True),
    include_past: bool = Query(True),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[AdminEventOut]:
    conditions = []
    if not include_inactive:
        conditions.append(Event.is_active.is_(True))
    if not include_past:
        conditions.append(Event.end_at >= now_utc())
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(or_(Event.name.ilike(pattern), Event.venue.ilike(pattern)))

    rows = db.scalars(
        select(Event)
        .where(*conditions)
        # Soonest first, so the working set is whatever is coming up next.
        .order_by(Event.start_at.asc(), Event.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [AdminEventOut.from_event(row) for row in rows]


@router.get("/events/{event_id}", response_model=AdminEventOut)
@limiter.limit("20/minute")
def get_event(
    request: Request,
    event_id: str = Path(pattern=ID_PATTERN),
    db: Session = Depends(get_db),
) -> AdminEventOut:
    row = db.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return AdminEventOut.from_event(row)


def _mirror_or_keep(
    url: str | None, *, wanted: bool, kind: str
) -> tuple[str | None, bool, str | None]:
    """Mirror media to R2 if asked and configured. Never fatal.

    A failed mirror keeps the original URL — media that works today beats none — and
    warns. The client falls back to a generated poster if that URL later breaks.

    Worth being clear about what a failure costs beyond a broken card: an unmirrored URL
    means every visitor's browser fetches from that third-party host, handing it their IP
    and the page they were on. So the warning is not cosmetic, and the honest fix for a
    URL that will not mirror is usually to drop it rather than to ship it as-is.
    """
    if not url or not wanted:
        return url, False, None
    # Already ours. Without this, editing an event re-downloads its own R2 object and
    # uploads it again under a fresh key, leaving the old one orphaned in the bucket —
    # once per edit, forever. The admin form does send a "don't re-mirror" flag when it
    # loads an event, but a check that depends on the client getting a checkbox right is
    # not a check.
    base = settings.r2_public_base_url.rstrip("/")
    if base and url.startswith(f"{base}/"):
        return url, False, None
    if not settings.r2_enabled:
        return url, False, f"R2 is not configured, so the {kind} was not mirrored."

    # A TikTok link is a page, not a file. yt-dlp fetches the video behind it, so pasting
    # a share link works the same as pasting a direct URL.
    #
    # This runs only past the r2_enabled gate above, and that ordering is load-bearing:
    # downloading a video we have nowhere to put would be pure waste, and the URL we would
    # be left storing still could not play.
    if kind == "video" and is_resolvable_video_page(url):
        try:
            body, content_type = download_video_page(url)
            return mirror_bytes_to_r2(body, content_type, kind=kind), True, None
        except (VideoResolveError, ImageMirrorError) as error:
            return url, False, str(error)

    try:
        return mirror_to_r2(url, kind=kind), True, None
    except ImageMirrorError as error:
        return url, False, str(error)


def _resolve_media(payload: EventWriteIn) -> tuple[str | None, str | None, bool, str | None]:
    """Resolve both media URLs. Returns (image_url, video_url, mirrored, warning).

    `mirrored` and the warning stay single-valued because that is what the admin UI
    shows; when both fail, the two messages are joined rather than one being dropped.
    """
    image_url, image_mirrored, image_warning = _mirror_or_keep(
        payload.image_url, wanted=payload.mirror_image, kind="image"
    )
    video_url, video_mirrored, video_warning = _mirror_or_keep(
        payload.video_url, wanted=payload.mirror_video, kind="video"
    )
    warnings = [w for w in (image_warning, video_warning) if w]
    return (
        image_url,
        video_url,
        image_mirrored or video_mirrored,
        " ".join(warnings) or None,
    )


def _tag_rows(payload: EventWriteIn) -> list[EventTag]:
    """The event's *additional* categories as tag rows.

    The primary vibe is dropped if the form happens to include it: it lives on the
    events row, and storing it twice would mean two places to keep in step.
    """
    extra = {tag.value for tag in payload.tags} - {payload.vibe.value}
    return [EventTag(tag=value) for value in sorted(extra)]


@router.post("/events", response_model=EventWriteOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_events(
    request: Request,
    payload: EventWriteIn,
    force: bool = Query(False, description="Save even when duplicates were found."),
    db: Session = Depends(get_db),
) -> EventWriteOut:
    duration = payload.ends_at_local - payload.starts_at_local

    if payload.recurrence is not None:
        occurrences = expand_occurrences(
            first_start_local=payload.starts_at_local,
            duration=duration,
            weekdays=[day.index for day in payload.recurrence.weekdays],
            until_local=payload.recurrence.until_local_date,
            limit=settings.max_series_occurrences,
        )
        if not occurrences:
            raise HTTPException(
                status_code=422,
                detail="That recurrence produced no dates — check the end date.",
            )
    else:
        occurrences = [
            (vegas_local_to_utc(payload.starts_at_local), vegas_local_to_utc(payload.ends_at_local))
        ]

    if not force:
        collisions = [
            DuplicateWarning(
                attempted_start_local=to_local_string(start),
                existing=[AdminEventOut.from_event(match) for match in matches],
            )
            for start, _ in occurrences
            if (matches := find_possible_duplicates(db, name=payload.name, venue=payload.venue, start_at=start))
        ]
        if collisions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "reason": "possible_duplicates",
                    "collisions": [item.model_dump(mode="json") for item in collisions],
                },
            )

    image_url, video_url, mirrored, warning = _resolve_media(payload)

    created = [
        Event(
            name=payload.name,
            venue=payload.venue,
            neighborhood=payload.neighborhood,
            address=payload.address,
            start_at=start,
            end_at=end,
            vibe=payload.vibe.value,
            alcohol_free=payload.alcohol_free,
            tags=_tag_rows(payload),
            price_tier=payload.price_tier.value,
            price_note=payload.price_note,
            hook=payload.hook,
            description=payload.description,
            image_url=image_url,
            video_url=video_url,
            ticket_url=payload.ticket_url,
            source_url=payload.source_url,
            is_active=payload.is_active,
            is_sample=False,
        )
        for start, end in occurrences
    ]
    db.add_all(created)
    db.commit()
    # Clears the sample-data banner flag and the tips the public list serves.
    cache.invalidate()

    return EventWriteOut(
        created=[AdminEventOut.from_event(event) for event in created],
        media_mirrored=mirrored,
        media_warning=warning,
    )


@router.put("/events/{event_id}", response_model=EventUpdateOut)
@limiter.limit("20/minute")
def replace_event(
    request: Request,
    payload: EventWriteIn,
    event_id: str = Path(pattern=ID_PATTERN),
    db: Session = Depends(get_db),
) -> EventUpdateOut:
    row = db.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    if payload.recurrence is not None:
        raise HTTPException(
            status_code=422,
            detail="A series is generated once on create; edit each night individually.",
        )

    # An edit is the other way an unmirrored third-party URL gets onto a card, and it
    # used to discard the outcome entirely — adding a video that failed to copy said
    # nothing at all.
    image_url, video_url, mirrored, warning = _resolve_media(payload)

    row.name = payload.name
    row.venue = payload.venue
    row.neighborhood = payload.neighborhood
    row.address = payload.address
    row.start_at = vegas_local_to_utc(payload.starts_at_local)
    row.end_at = vegas_local_to_utc(payload.ends_at_local)
    row.vibe = payload.vibe.value
    row.alcohol_free = payload.alcohol_free
    # Replaced wholesale rather than merged: the form always sends the complete set, and
    # a merge would make removing a category impossible.
    row.tags = _tag_rows(payload)
    row.price_tier = payload.price_tier.value
    row.price_note = payload.price_note
    row.hook = payload.hook
    row.description = payload.description
    row.image_url = image_url
    row.video_url = video_url
    row.ticket_url = payload.ticket_url
    row.source_url = payload.source_url
    row.is_active = payload.is_active
    # Editing a sample event makes it real; that is how the banner clears itself.
    row.is_sample = False

    db.commit()
    cache.invalidate()
    return EventUpdateOut(
        **AdminEventOut.from_event(row).model_dump(),
        media_mirrored=mirrored,
        media_warning=warning,
    )


@router.post("/events/{event_id}/deactivate", response_model=AdminEventOut)
@limiter.limit("20/minute")
def deactivate_event(
    request: Request,
    event_id: str = Path(pattern=ID_PATTERN),
    db: Session = Depends(get_db),
) -> AdminEventOut:
    """Pull an event from the stack. Events are flagged, never deleted."""
    row = db.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    row.is_active = False
    db.commit()
    cache.invalidate()
    return AdminEventOut.from_event(row)


# ------------------------------------------------------------------ diagnostics


@router.get("/diagnostics/client")
@limiter.limit("30/minute")
def client_diagnostics(request: Request) -> dict:
    """What the server thinks the caller's address is, and where it got that from.

    Exists because the alternative was guessing. Rate limiting is keyed on this, and
    getting it wrong is invisible from outside: every visitor sharing one bucket looks
    exactly like normal operation until real traffic arrives and starts getting 429s.
    Being able to ask the deployed API directly turns that into a five-second check.
    """
    sources = resolve_client_sources(request)
    return {
        "resolved_key": client_ip(request),
        "trust_proxy_headers": settings.trust_proxy_headers,
        "sources": sources,
        # The tell: if this is true, the socket peer is a proxy and keying on it would
        # have put every visitor in the same bucket.
        "behind_proxy": bool(sources["cf_connecting_ip"] or sources["x_forwarded_for_raw"]),
        # How to verify the Cloudflare Transform Rule without guessing: call this
        # through api.vegasthisweekend.com and secret_matches must be true, then call
        # the raw *.up.railway.app hostname and it must be false. Only once both hold
        # is it safe to set REQUIRE_PROXY_SECRET.
        "proxy_secret": secret_status(request),
    }


# ------------------------------------------------------- bulk extraction queue


class BulkSubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # One URL per line. Parsed server-side so the same rules apply however it is called.
    urls: str = Field(min_length=1, max_length=100_000)


class BulkSubmitOut(BaseModel):
    batch_id: str
    queued: int
    # Lines that were not usable URLs, echoed back so a typo is visible immediately
    # rather than becoming a failed draft ten minutes later.
    rejected: list[str]


class QueueItemOut(BaseModel):
    id: str
    url: str
    status: str
    draft: dict | None
    error: str | None
    event_id: str | None
    created_at: datetime
    # True when extraction thinks this is a residency. Never acted on automatically —
    # a wrong guess in bulk would add dozens of events to delete one at a time.
    looks_recurring: bool


@router.post("/extractions", response_model=BulkSubmitOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("6/minute")
def submit_extractions(
    request: Request, payload: BulkSubmitIn, db: Session = Depends(get_db)
) -> BulkSubmitOut:
    """Queue a block of pasted URLs for extraction."""
    urls, rejected = parse_urls(payload.urls)
    if not urls:
        raise HTTPException(
            status_code=422,
            detail="No usable URLs in that. Each line should be an http(s) link.",
        )
    try:
        batch_id, drafts = submit_batch(db, urls)
    except BulkExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return BulkSubmitOut(batch_id=batch_id, queued=len(drafts), rejected=rejected)


@router.get("/extractions", response_model=list[QueueItemOut])
@limiter.limit("60/minute")
def list_extractions(
    request: Request,
    refresh: bool = Query(True, description="Check finished batches before listing."),
    db: Session = Depends(get_db),
) -> list[QueueItemOut]:
    """The queue. Collecting finished batches happens here rather than on a schedule —
    there is no worker process, and the person looking at the queue is the only one who
    needs it to be current."""
    if refresh:
        collect_batches(db)

    rows = db.scalars(
        select(ExtractionDraft)
        .where(ExtractionDraft.status != "discarded")
        .order_by(ExtractionDraft.created_at.desc())
        .limit(200)
    ).all()

    return [
        QueueItemOut(
            id=row.id,
            url=row.url,
            status=row.status,
            draft=row.draft,
            error=row.error,
            event_id=row.event_id,
            created_at=row.created_at,
            looks_recurring=bool((row.draft or {}).get("recurrence", {}).get("repeats")),
        )
        for row in rows
    ]


@router.post("/extractions/{draft_id}/discard", response_model=QueueItemOut)
@limiter.limit("60/minute")
def discard_extraction(
    request: Request,
    draft_id: str = Path(pattern=ID_PATTERN),
    db: Session = Depends(get_db),
) -> QueueItemOut:
    row = db.get(ExtractionDraft, draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    row.status = "discarded"
    db.commit()
    return QueueItemOut(
        id=row.id,
        url=row.url,
        status=row.status,
        draft=row.draft,
        error=row.error,
        event_id=row.event_id,
        created_at=row.created_at,
        looks_recurring=False,
    )


@router.post("/extractions/{draft_id}/mark-approved", response_model=QueueItemOut)
@limiter.limit("60/minute")
def mark_extraction_approved(
    request: Request,
    event_id: str = Query(pattern=ID_PATTERN),
    draft_id: str = Path(pattern=ID_PATTERN),
    db: Session = Depends(get_db),
) -> QueueItemOut:
    """Link a draft to the event it produced, once the normal create endpoint saved it.

    Kept separate from creating the event on purpose. The review form already posts to
    /admin/events with every validation and the duplicate check attached, and routing
    bulk approvals through a second write path would mean two places for those rules to
    live — and one of them would eventually be wrong.
    """
    row = db.get(ExtractionDraft, draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    row.status = "approved"
    row.event_id = event_id
    db.commit()
    return QueueItemOut(
        id=row.id,
        url=row.url,
        status=row.status,
        draft=row.draft,
        error=row.error,
        event_id=row.event_id,
        created_at=row.created_at,
        looks_recurring=False,
    )


# ------------------------------------------------------------------ stats


@router.get("/stats")
@limiter.limit("30/minute")
def read_stats(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="How many days back to include."),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate interaction counts, for the dashboard.

    Not a response_model: the shape is a set of nested count dictionaries keyed by
    metric name, and spelling that out as Pydantic models would add a layer to keep in
    step with the Metric enum for no validation benefit on a read-only admin endpoint.
    """
    return summary(db, days=days)


# ------------------------------------------------------------------ insider tips


@router.get("/tips", response_model=list[AdminTipOut])
@limiter.limit("20/minute")
def list_tips(request: Request, db: Session = Depends(get_db)) -> list[AdminTipOut]:
    rows = db.scalars(
        select(InsiderTip).order_by(InsiderTip.priority.desc(), InsiderTip.created_at.desc())
    ).all()
    return [AdminTipOut.model_validate(row) for row in rows]


@router.post("/tips", response_model=AdminTipOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_tip(request: Request, payload: TipWriteIn, db: Session = Depends(get_db)) -> AdminTipOut:
    tip = InsiderTip(
        venue=payload.venue,
        vibe=payload.vibe.value if payload.vibe else None,
        tip=payload.tip,
        is_active=payload.is_active,
        priority=payload.priority,
    )
    db.add(tip)
    db.commit()
    cache.invalidate()
    return AdminTipOut.model_validate(tip)


@router.put("/tips/{tip_id}", response_model=AdminTipOut)
@limiter.limit("20/minute")
def replace_tip(
    request: Request,
    payload: TipWriteIn,
    tip_id: str = Path(pattern=ID_PATTERN),
    db: Session = Depends(get_db),
) -> AdminTipOut:
    tip = db.get(InsiderTip, tip_id)
    if tip is None:
        raise HTTPException(status_code=404, detail="Tip not found.")
    tip.venue = payload.venue
    tip.vibe = payload.vibe.value if payload.vibe else None
    tip.tip = payload.tip
    tip.is_active = payload.is_active
    tip.priority = payload.priority
    db.commit()
    cache.invalidate()
    return AdminTipOut.model_validate(tip)


@router.delete("/tips/{tip_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
def delete_tip(
    request: Request,
    tip_id: str = Path(pattern=ID_PATTERN),
    db: Session = Depends(get_db),
) -> None:
    tip = db.get(InsiderTip, tip_id)
    if tip is None:
        raise HTTPException(status_code=404, detail="Tip not found.")
    db.delete(tip)
    db.commit()
    cache.invalidate()


# ------------------------------------------------------------------ status


@router.get("/status")
@limiter.limit("20/minute")
def admin_status(request: Request, db: Session = Depends(get_db)) -> dict:
    """What the panel needs to know about this deployment's capabilities."""
    return {
        "extraction_enabled": settings.extraction_enabled,
        "extraction_model": settings.anthropic_model if settings.extraction_enabled else None,
        "r2_enabled": settings.r2_enabled,
        "environment": settings.environment,
        "event_count": db.scalar(select(func.count()).select_from(Event)) or 0,
        "sample_event_count": db.scalar(
            select(func.count()).select_from(Event).where(Event.is_sample.is_(True))
        )
        or 0,
    }
