"""Bulk URL extraction through the Message Batches API.

Why batches rather than a loop of ordinary calls: they are half price, and the workflow
is already asynchronous — John pastes a set of URLs and comes back to review them. The
cost difference is roughly $13.50 a month against $27 at fifty events a week, measured.

The awkward part, and the reason this is its own module: `client.messages.parse()` does
the Pydantic round-trip for us on a single call, but a batch takes raw request params, so
the JSON schema has to be produced here and the response validated by hand. Getting that
wrong fails silently — the batch succeeds and every draft is unusable — so the schema is
built from the same Pydantic model the single-call path uses rather than written out
twice.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .extraction import (
    EFFORT,
    MAX_TOKENS,
    PROMPT_CACHING,
    SYSTEM_PROMPT,
    WEB_FETCH_MAX_CONTENT_TOKENS,
    WEB_FETCH_MAX_USES,
    ExtractionResult,
    _user_content,
)
from .models import ExtractionDraft
from .timewindow import now_vegas

logger = logging.getLogger(__name__)

# The API's own ceiling is far higher; this is a guard against one paste turning into a
# bill nobody intended. At the measured ~$0.06/URL batched, 100 URLs is about $6.
MAX_URLS_PER_SUBMISSION = 100


class BulkExtractionError(RuntimeError):
    """Raised when a batch could not be submitted. The message is shown to John."""


def _result_schema() -> dict[str, Any]:
    """The JSON schema for ExtractionResult, in the shape structured outputs want.

    Derived from the Pydantic model rather than hand-written, so the batch path and the
    single-call path can never drift apart. Every model in the tree sets
    `extra="forbid"`, which is what makes Pydantic emit `additionalProperties: false` —
    required by structured outputs, and the thing most likely to be missed if this were
    maintained by hand.
    """
    return ExtractionResult.model_json_schema()


def _request_params(url: str) -> dict[str, Any]:
    """One batch entry's params. Mirrors the single-call request deliberately."""
    settings = get_settings()

    fetch_tool: dict[str, Any] = {
        "type": "web_fetch_20260209",
        "name": "web_fetch",
        "max_uses": WEB_FETCH_MAX_USES,
    }
    if WEB_FETCH_MAX_CONTENT_TOKENS is not None:
        fetch_tool["max_content_tokens"] = WEB_FETCH_MAX_CONTENT_TOKENS

    params: dict[str, Any] = {
        "model": settings.anthropic_model,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "thinking": {"type": "adaptive"},
        "tools": [fetch_tool],
        "output_config": {"format": {"type": "json_schema", "schema": _result_schema()}},
        "messages": [
            {"role": "user", "content": _user_content(url=url, text=None, today=now_vegas().date())}
        ],
    }
    if EFFORT is not None:
        params["output_config"]["effort"] = EFFORT
    if PROMPT_CACHING:
        # Worth more here than on a single call: every request in the batch shares the
        # same system prompt and tool definitions, so after the first one they are read
        # from cache instead of paid for per URL.
        params["cache_control"] = {"type": "ephemeral"}
    return params


def submit(db: Session, urls: list[str]) -> tuple[str, list[ExtractionDraft]]:
    """Queue a set of URLs as one batch. Returns the batch id and the created drafts."""
    settings = get_settings()
    if not settings.extraction_enabled:
        raise BulkExtractionError(
            "ANTHROPIC_API_KEY is not configured, so extraction is unavailable."
        )
    if not urls:
        raise BulkExtractionError("No URLs to extract.")
    if len(urls) > MAX_URLS_PER_SUBMISSION:
        raise BulkExtractionError(
            f"That is {len(urls)} URLs; {MAX_URLS_PER_SUBMISSION} is the limit per submission."
        )

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Rows first, so their ids can be the batch's custom_ids. Results come back in
    # arbitrary order and are matched by custom_id, never by position.
    drafts = [ExtractionDraft(url=url, status="queued") for url in urls]
    db.add_all(drafts)
    db.flush()

    requests = [
        {"custom_id": draft.id, "params": _request_params(draft.url)} for draft in drafts
    ]

    try:
        batch = client.messages.batches.create(requests=requests)
    except anthropic.APIStatusError as error:
        db.rollback()
        raise BulkExtractionError(f"Claude API error ({error.status_code}).") from error
    except anthropic.APIConnectionError as error:
        db.rollback()
        raise BulkExtractionError("Could not reach the Claude API.") from error

    for draft in drafts:
        draft.batch_id = batch.id
        draft.status = "running"
    db.commit()

    logger.info("bulk extraction submitted batch=%s urls=%d", batch.id, len(urls))
    return batch.id, drafts


def _draft_payload(raw: str, url: str) -> tuple[dict | None, str | None]:
    """Validate one batch result into the shape the review form expects."""
    from .routers.admin import build_extract_out  # local import: avoids a cycle

    try:
        result = ExtractionResult.model_validate_json(raw)
    except Exception as error:  # noqa: BLE001 - any malformed payload is the same to us
        return None, f"Could not read the model's response: {error}"[:400]

    if not result.found_event or result.event is None:
        return None, result.notes or "No event found on that page."

    try:
        return build_extract_out(result, source_url=url).model_dump(mode="json"), None
    except Exception as error:  # noqa: BLE001
        return None, f"Draft could not be built: {error}"[:400]


def collect(db: Session) -> dict[str, int]:
    """Pull in results for any batch that has finished.

    Safe to call repeatedly and from anywhere — it is driven entirely by what is in the
    database, so a restart mid-batch loses nothing and the admin can simply refresh.
    """
    settings = get_settings()
    if not settings.extraction_enabled:
        return {"checked": 0, "ready": 0, "failed": 0}

    batch_ids = set(
        db.scalars(
            select(ExtractionDraft.batch_id).where(
                ExtractionDraft.status == "running", ExtractionDraft.batch_id.is_not(None)
            )
        ).all()
    )
    if not batch_ids:
        return {"checked": 0, "ready": 0, "failed": 0}

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    ready = failed = 0

    for batch_id in batch_ids:
        try:
            batch = client.messages.batches.retrieve(batch_id)
        except Exception as error:  # noqa: BLE001
            logger.warning("could not retrieve batch %s: %s", batch_id, error)
            continue
        if batch.processing_status != "ended":
            continue

        pending = {
            draft.id: draft
            for draft in db.scalars(
                select(ExtractionDraft).where(
                    ExtractionDraft.batch_id == batch_id, ExtractionDraft.status == "running"
                )
            ).all()
        }

        for entry in client.messages.batches.results(batch_id):
            draft = pending.pop(entry.custom_id, None)
            if draft is None:
                continue

            if entry.result.type != "succeeded":
                draft.status = "failed"
                draft.error = f"Extraction {entry.result.type}."
                failed += 1
                continue

            text = next(
                (block.text for block in entry.result.message.content if block.type == "text"),
                None,
            )
            if text is None:
                draft.status = "failed"
                draft.error = "The model returned no content."
                failed += 1
                continue

            payload, error = _draft_payload(text, draft.url)
            if payload is None:
                draft.status = "failed"
                draft.error = error
                failed += 1
            else:
                draft.status = "ready"
                draft.draft = payload
                ready += 1

        # Anything the batch never reported on. Left visible rather than stuck on
        # "running" forever, which would look like the queue had hung.
        for orphan in pending.values():
            orphan.status = "failed"
            orphan.error = "The batch finished without a result for this URL."
            failed += 1

    db.commit()
    logger.info("bulk extraction collected batches=%d ready=%d failed=%d", len(batch_ids), ready, failed)
    return {"checked": len(batch_ids), "ready": ready, "failed": failed}


def parse_urls(blob: str) -> tuple[list[str], list[str]]:
    """Split a pasted block into URLs, keeping order and dropping duplicates.

    Returns (urls, rejected). Anything that is not http(s) is rejected rather than sent —
    a typo should be visible immediately, not turn into a failed draft ten minutes later.
    """
    from .extraction import _clean_url

    urls: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()

    for raw in blob.splitlines():
        line = raw.strip()
        if not line:
            continue
        cleaned = _clean_url(line)
        if cleaned is None:
            rejected.append(line[:120])
        elif cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)

    return urls, rejected
