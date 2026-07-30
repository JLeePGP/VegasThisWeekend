"""Bulk URL extraction.

No test here reaches the network: conftest forces ANTHROPIC_API_KEY empty, and the
batch client is patched. What is worth testing is everything around the API call —
parsing, matching results back to the right draft, and the failure paths, since a batch
that silently maps results to the wrong URLs would be very hard to notice by eye.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import bulk_extraction
from app.bulk_extraction import parse_urls
from app.models import ExtractionDraft

EVENTBRITE = "https://www.eventbrite.com/e/a-thing-tickets-123"
VENUE = "https://example.com/events/thing"


class TestParseUrls:
    def test_splits_on_newlines(self):
        urls, rejected = parse_urls(f"{EVENTBRITE}\n{VENUE}")
        assert urls == [EVENTBRITE, VENUE]
        assert rejected == []

    def test_ignores_blank_lines_and_whitespace(self):
        urls, _ = parse_urls(f"\n  {EVENTBRITE}  \n\n\n  {VENUE}\n  \n")
        assert urls == [EVENTBRITE, VENUE]

    def test_drops_duplicates_but_keeps_order(self):
        urls, _ = parse_urls("\n".join([VENUE, EVENTBRITE, VENUE]))
        assert urls == [VENUE, EVENTBRITE]

    def test_rejects_non_http_lines(self):
        urls, rejected = parse_urls(f"{EVENTBRITE}\nnot a url\njavascript:alert(1)")
        assert urls == [EVENTBRITE]
        assert rejected == ["not a url", "javascript:alert(1)"]

    def test_rejects_rather_than_silently_dropping(self):
        """A typo should be visible at paste time, not become a failed draft later."""
        _, rejected = parse_urls("htps://typo.example.com/event")
        assert rejected == ["htps://typo.example.com/event"]


def _fake_client(batch_id="msgbatch_1", results=None, processing_status="ended"):
    """A stand-in for the Anthropic client covering only what this module calls."""
    created = SimpleNamespace(id=batch_id)
    batch = SimpleNamespace(id=batch_id, processing_status=processing_status)

    class Batches:
        def create(self, requests):
            Batches.last_requests = requests
            return created

        def retrieve(self, _id):
            return batch

        def results(self, _id):
            return iter(results or [])

    return SimpleNamespace(messages=SimpleNamespace(batches=Batches()))


def _succeeded(custom_id, payload):
    text_block = SimpleNamespace(type="text", text=json.dumps(payload))
    return SimpleNamespace(
        custom_id=custom_id,
        result=SimpleNamespace(
            type="succeeded", message=SimpleNamespace(content=[text_block])
        ),
    )


def _result_payload(name="A Real Event", *, found=True, repeats=False):
    return {
        "found_event": found,
        "event": None
        if not found
        else {
            "name": name,
            "venue": "A Venue",
            "neighborhood": "Downtown",
            "address": "1 Main St, Las Vegas, NV",
            "starts_at_local": "2026-09-04T20:00",
            "ends_at_local": "2026-09-04T23:00",
            "vibe": "music",
            "tags": ["local"],
            "alcohol_free": False,
            "price_tier": "budget",
            "price_note": None,
            "hook": "A hook.",
            "description": "A description.",
            "ticket_url": None,
            "image_url": None,
        },
        "recurrence": {"repeats": repeats, "weekdays": [], "until_local_date": None},
        "uncertain_fields": [],
        "notes": "",
    }


@pytest.fixture
def enabled(monkeypatch):
    """Pretend extraction is configured, without a key ever being present."""
    settings = bulk_extraction.get_settings()
    monkeypatch.setattr(type(settings), "extraction_enabled", property(lambda _self: True))
    yield


class TestSubmit:
    def test_creates_a_draft_per_url(self, db, enabled):
        client = _fake_client()
        with patch("anthropic.Anthropic", return_value=client):
            batch_id, drafts = bulk_extraction.submit(db, [EVENTBRITE, VENUE])

        assert batch_id == "msgbatch_1"
        assert len(drafts) == 2
        assert {d.status for d in drafts} == {"running"}
        assert db.query(ExtractionDraft).count() == 2

    def test_custom_ids_are_the_draft_ids(self, db, enabled):
        """Results come back in arbitrary order and are matched by custom_id. If these
        were positional, a slow URL finishing last would attach its draft to the wrong
        row — wrong data that looks entirely plausible."""
        client = _fake_client()
        with patch("anthropic.Anthropic", return_value=client):
            _, drafts = bulk_extraction.submit(db, [EVENTBRITE, VENUE])

        sent = {r["custom_id"] for r in type(client.messages.batches).last_requests}
        assert sent == {d.id for d in drafts}

    def test_rejects_an_empty_list(self, db, enabled):
        with pytest.raises(bulk_extraction.BulkExtractionError):
            bulk_extraction.submit(db, [])

    def test_rejects_more_than_the_cap(self, db, enabled):
        too_many = [f"https://example.com/{i}" for i in range(101)]
        with pytest.raises(bulk_extraction.BulkExtractionError, match="limit"):
            bulk_extraction.submit(db, too_many)

    def test_refuses_when_extraction_is_not_configured(self, db):
        with pytest.raises(bulk_extraction.BulkExtractionError, match="ANTHROPIC_API_KEY"):
            bulk_extraction.submit(db, [EVENTBRITE])

    def test_no_drafts_survive_a_failed_submission(self, db, enabled):
        """A batch that never reached the API must not leave rows stuck on 'queued'."""
        import anthropic

        class Exploding:
            def create(self, requests):
                raise anthropic.APIConnectionError(request=None)

        client = SimpleNamespace(messages=SimpleNamespace(batches=Exploding()))
        with patch("anthropic.Anthropic", return_value=client):
            with pytest.raises(bulk_extraction.BulkExtractionError):
                bulk_extraction.submit(db, [EVENTBRITE])

        assert db.query(ExtractionDraft).count() == 0


class TestCollect:
    def _submitted(self, db, urls):
        with patch("anthropic.Anthropic", return_value=_fake_client()):
            _, drafts = bulk_extraction.submit(db, urls)
        return drafts

    def test_matches_results_to_the_right_draft(self, db, enabled):
        drafts = self._submitted(db, [EVENTBRITE, VENUE])
        first, second = drafts
        # Deliberately returned in the opposite order to submission.
        results = [
            _succeeded(second.id, _result_payload("Second Event")),
            _succeeded(first.id, _result_payload("First Event")),
        ]
        with patch("anthropic.Anthropic", return_value=_fake_client(results=results)):
            counts = bulk_extraction.collect(db)

        assert counts["ready"] == 2
        db.refresh(first)
        db.refresh(second)
        assert first.draft["draft"]["name"] == "First Event"
        assert second.draft["draft"]["name"] == "Second Event"

    def test_carries_the_new_fields_through(self, db, enabled):
        draft = self._submitted(db, [EVENTBRITE])[0]
        results = [_succeeded(draft.id, _result_payload())]
        with patch("anthropic.Anthropic", return_value=_fake_client(results=results)):
            bulk_extraction.collect(db)

        db.refresh(draft)
        payload = draft.draft["draft"]
        assert payload["address"] == "1 Main St, Las Vegas, NV"
        assert payload["tags"] == ["local"]
        assert payload["alcohol_free"] is False
        assert payload["source_url"] == EVENTBRITE

    def test_primary_vibe_is_stripped_from_tags(self, db, enabled):
        draft = self._submitted(db, [EVENTBRITE])[0]
        payload = _result_payload()
        payload["event"]["tags"] = ["music", "local"]  # music is also the primary
        with patch("anthropic.Anthropic", return_value=_fake_client(results=[_succeeded(draft.id, payload)])):
            bulk_extraction.collect(db)

        db.refresh(draft)
        assert draft.draft["draft"]["tags"] == ["local"]

    def test_a_page_with_no_event_becomes_a_failure_not_a_draft(self, db, enabled):
        draft = self._submitted(db, [EVENTBRITE])[0]
        payload = _result_payload(found=False)
        payload["notes"] = "Instagram requires a login."
        with patch("anthropic.Anthropic", return_value=_fake_client(results=[_succeeded(draft.id, payload)])):
            counts = bulk_extraction.collect(db)

        db.refresh(draft)
        assert counts["failed"] == 1
        assert draft.status == "failed"
        assert draft.error == "Instagram requires a login."

    def test_an_errored_result_is_recorded(self, db, enabled):
        draft = self._submitted(db, [EVENTBRITE])[0]
        entry = SimpleNamespace(custom_id=draft.id, result=SimpleNamespace(type="errored"))
        with patch("anthropic.Anthropic", return_value=_fake_client(results=[entry])):
            bulk_extraction.collect(db)

        db.refresh(draft)
        assert draft.status == "failed" and "errored" in draft.error

    def test_malformed_json_fails_that_draft_only(self, db, enabled):
        good, bad = self._submitted(db, [EVENTBRITE, VENUE])
        results = [
            _succeeded(good.id, _result_payload("Fine")),
            SimpleNamespace(
                custom_id=bad.id,
                result=SimpleNamespace(
                    type="succeeded",
                    message=SimpleNamespace(content=[SimpleNamespace(type="text", text="{not json")]),
                ),
            ),
        ]
        with patch("anthropic.Anthropic", return_value=_fake_client(results=results)):
            counts = bulk_extraction.collect(db)

        assert counts == {"checked": 1, "ready": 1, "failed": 1}
        db.refresh(good)
        db.refresh(bad)
        assert good.status == "ready"
        assert bad.status == "failed"

    def test_a_draft_the_batch_never_reported_does_not_hang(self, db, enabled):
        """Otherwise it sits on 'running' forever and the queue looks stuck."""
        reported, missing = self._submitted(db, [EVENTBRITE, VENUE])
        results = [_succeeded(reported.id, _result_payload())]
        with patch("anthropic.Anthropic", return_value=_fake_client(results=results)):
            bulk_extraction.collect(db)

        db.refresh(missing)
        assert missing.status == "failed"
        assert "without a result" in missing.error

    def test_an_unfinished_batch_is_left_alone(self, db, enabled):
        draft = self._submitted(db, [EVENTBRITE])[0]
        client = _fake_client(processing_status="in_progress")
        with patch("anthropic.Anthropic", return_value=client):
            counts = bulk_extraction.collect(db)

        db.refresh(draft)
        assert draft.status == "running"
        assert counts["ready"] == 0

    def test_collect_is_a_no_op_with_nothing_running(self, db, enabled):
        assert bulk_extraction.collect(db) == {"checked": 0, "ready": 0, "failed": 0}

    def test_recurrence_is_carried_but_never_expanded(self, db, enabled):
        """Bulk must not turn one URL into 26 events on a guess."""
        draft = self._submitted(db, [EVENTBRITE])[0]
        payload = _result_payload(repeats=True)
        payload["recurrence"]["weekdays"] = ["friday"]
        with patch("anthropic.Anthropic", return_value=_fake_client(results=[_succeeded(draft.id, payload)])):
            bulk_extraction.collect(db)

        db.refresh(draft)
        assert draft.draft["recurrence"]["repeats"] is True
        # One draft, one row. Expansion is a decision made in the review form.
        assert db.query(ExtractionDraft).count() == 1


class TestSchemaGeneration:
    def test_schema_forbids_extra_properties(self):
        """Structured outputs require additionalProperties: false everywhere. It comes
        from extra='forbid' on the Pydantic models, so this asserts the coupling rather
        than the literal schema."""
        schema = bulk_extraction._result_schema()
        defs = schema.get("$defs", {})
        objects = [schema, *[d for d in defs.values() if d.get("type") == "object"]]
        assert objects, "expected nested object definitions"
        for obj in objects:
            if obj.get("type") == "object":
                assert obj.get("additionalProperties") is False, obj.get("title")

    def test_schema_includes_the_new_fields(self):
        schema = bulk_extraction._result_schema()
        event = schema["$defs"]["ExtractedEvent"]["properties"]
        assert {"address", "tags", "alcohol_free"} <= set(event)


class TestEndpoints:
    def test_submit_requires_auth(self, client):
        assert client.post("/admin/extractions", json={"urls": EVENTBRITE}).status_code == 401

    def test_list_requires_auth(self, client):
        assert client.get("/admin/extractions").status_code == 401

    def test_submit_rejects_a_blob_with_no_urls(self, admin_client, enabled):
        response = admin_client.post("/admin/extractions", json={"urls": "nonsense\nmore nonsense"})
        assert response.status_code == 422

    def test_submit_echoes_rejected_lines(self, admin_client, db, enabled):
        with patch("anthropic.Anthropic", return_value=_fake_client()):
            body = admin_client.post(
                "/admin/extractions", json={"urls": f"{EVENTBRITE}\nnot-a-url"}
            ).json()
        assert body["queued"] == 1
        assert body["rejected"] == ["not-a-url"]

    def test_queue_lists_drafts(self, admin_client, db, enabled):
        with patch("anthropic.Anthropic", return_value=_fake_client()):
            admin_client.post("/admin/extractions", json={"urls": EVENTBRITE})
        rows = admin_client.get("/admin/extractions", params={"refresh": "false"}).json()
        assert len(rows) == 1
        assert rows[0]["url"] == EVENTBRITE
        assert rows[0]["status"] == "running"

    def test_discard_hides_a_draft(self, admin_client, db, enabled):
        with patch("anthropic.Anthropic", return_value=_fake_client()):
            admin_client.post("/admin/extractions", json={"urls": EVENTBRITE})
        draft_id = db.query(ExtractionDraft).one().id

        admin_client.post(f"/admin/extractions/{draft_id}/discard")
        rows = admin_client.get("/admin/extractions", params={"refresh": "false"}).json()
        assert rows == []

    def test_marking_approved_links_the_event(self, admin_client, db, enabled):
        with patch("anthropic.Anthropic", return_value=_fake_client()):
            admin_client.post("/admin/extractions", json={"urls": EVENTBRITE})
        draft_id = db.query(ExtractionDraft).one().id
        event_id = "a" * 32

        body = admin_client.post(
            f"/admin/extractions/{draft_id}/mark-approved", params={"event_id": event_id}
        ).json()
        assert body["status"] == "approved"
        assert body["event_id"] == event_id
