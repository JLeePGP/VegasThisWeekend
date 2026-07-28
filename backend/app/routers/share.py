"""Anonymous share lists.

A share list is a random token plus an ordered list of event ids. No user identity,
no IP, nothing that ties it back to the person who created it.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..limiter import limiter
from ..models import Event, ShareList
from ..schemas import EventOut, ShareCreateIn, ShareCreateOut, ShareOut
from ..timewindow import now_utc
from ..tips import load_tip_buckets, match_tip

router = APIRouter(tags=["share"])
settings = get_settings()


@router.post("/share", response_model=ShareCreateOut, status_code=201)
@limiter.limit("10/minute")
def create_share(
    request: Request,
    payload: ShareCreateIn,
    db: Session = Depends(get_db),
) -> ShareCreateOut:
    if len(payload.event_ids) > settings.max_share_events:
        raise HTTPException(
            status_code=400,
            detail=f"A share list holds at most {settings.max_share_events} events.",
        )

    # Drop ids that do not resolve rather than failing the whole list — a saved list can
    # outlive an event that was pulled from the catalog.
    known = set(db.scalars(select(Event.id).where(Event.id.in_(payload.event_ids))).all())
    kept = [event_id for event_id in payload.event_ids if event_id in known]
    if not kept:
        raise HTTPException(status_code=400, detail="None of those events could be found.")

    share = ShareList(
        event_ids=kept,
        expires_at=now_utc() + timedelta(days=settings.share_ttl_days),
    )
    db.add(share)
    db.commit()

    return ShareCreateOut(token=share.token, expires_at=share.expires_at, path=f"/s/{share.token}")


@router.get("/share/{token}", response_model=ShareOut)
@limiter.limit("100/minute")
def get_share(
    request: Request,
    token: str = Path(pattern=r"^[0-9a-f]{32}$"),
    db: Session = Depends(get_db),
) -> ShareOut:
    share = db.get(ShareList, token)
    if share is None or share.expires_at < now_utc():
        raise HTTPException(status_code=404, detail="This link has expired or never existed.")

    rows = db.scalars(select(Event).where(Event.id.in_(share.event_ids))).all()
    by_id = {row.id: row for row in rows}
    buckets = load_tip_buckets(db)

    # Preserve the order the sender saved them in. Events that have since passed are
    # still returned: the recipient should see the list that was actually shared.
    events: list[EventOut] = []
    for event_id in share.event_ids:
        row = by_id.get(event_id)
        if row is None:
            continue
        item = EventOut.model_validate(row)
        item.insider_tip = match_tip(row, buckets)
        events.append(item)

    return ShareOut(token=share.token, expires_at=share.expires_at, events=events)
