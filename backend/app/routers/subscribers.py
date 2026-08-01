"""Newsletter signup.

The only endpoint in this project that accepts personal data, so the rules it works to
are worth stating where they are enforced:

* nothing about the request is stored beyond the address and which screen it came from —
  no IP, no user agent, no timestamped visit trail
* signing up twice is a no-op, and the response cannot be used to find out whether an
  address is already on the list
* the address is normalised before it is stored, because two rows for one person means
  mailing them twice

Sending is not done from here and is not planned to be. The list is exported to a
newsletter provider (`scripts/export_data.py` already writes every table nightly); this
endpoint's whole job is to collect addresses without handing every visitor to a
third-party form.
"""

from __future__ import annotations

from enum import Enum

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..limiter import limiter
from ..models import Subscriber

router = APIRouter(tags=["subscribers"])


class SignupSource(str, Enum):
    """Which surface converted. A closed set for the same reason metrics are closed:
    the endpoint is public, and a free string would let anyone write whatever they like
    into a column John reads."""

    LIST_END = "list_end"
    SAVED = "saved"


class SubscribeIn(BaseModel):
    email: EmailStr
    source: SignupSource

    @field_validator("email")
    @classmethod
    def normalise(cls, value: str) -> str:
        # Lowercased so the unique index does its job. RFC 5321 says the local part is
        # case-sensitive; no mail provider in practice agrees, and the failure mode of
        # honouring the RFC here is a duplicate subscriber rather than a lost one.
        return value.strip().lower()


class SubscribeOut(BaseModel):
    subscribed: bool


@router.post(
    "/subscribers", response_model=SubscribeOut, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit("5/minute")
def subscribe(
    request: Request,
    payload: SubscribeIn,
    db: Session = Depends(get_db),
) -> SubscribeOut:
    db.add(Subscriber(email=payload.email, source=payload.source.value))
    try:
        db.commit()
    except IntegrityError:
        # Already subscribed. Insert-and-catch rather than check-then-insert: the check
        # would race two submissions from the same person, and answering "that address is
        # already on the list" would turn a public endpoint into a way to test whether
        # someone else had signed up.
        db.rollback()

    return SubscribeOut(subscribed=True)
