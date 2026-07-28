"""The admin surface: auth, event writes, series, duplicates, tips."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.enums import Neighborhood, PriceTier, Vibe
from app.extraction import (
    ExtractedEvent,
    ExtractionError,
    ExtractionResult,
    RecurrenceHint,
)
from app.models import Event

# 7 Aug 2026 is a Friday, and Pacific is on daylight time (UTC-7) that week.
START_LOCAL = "2026-08-07T21:00"
END_LOCAL = "2026-08-08T01:00"
START_UTC = datetime(2026, 8, 8, 4, 0, tzinfo=timezone.utc)


def event_payload(**overrides) -> dict:
    payload = {
        "name": "Cactus Sessions",
        "venue": "The Velvet Cactus",
        "neighborhood": "Arts District",
        "starts_at_local": START_LOCAL,
        "ends_at_local": END_LOCAL,
        "vibe": "music",
        "price_tier": "budget",
        "price_note": "$18 advance",
        "hook": "Three touring bands in a room small enough to heckle the drummer",
        "description": "A tight three-band bill. Doors at eight, done by one.",
        # Off by default so no test reaches the network; one test flips it deliberately.
        "mirror_image": False,
    }
    payload.update(overrides)
    return payload


class TestAuth:
    def test_no_token_is_rejected(self, client):
        assert client.get("/admin/events").status_code == 401

    def test_wrong_token_is_rejected(self, client):
        response = client.get("/admin/events", headers={"Authorization": "Bearer nope"})
        assert response.status_code == 401

    def test_non_bearer_scheme_is_rejected(self, client):
        response = client.get("/admin/events", headers={"Authorization": "Basic abc123"})
        assert response.status_code == 401

    def test_valid_token_is_accepted(self, admin_client):
        assert admin_client.get("/admin/events").status_code == 200

    def test_every_admin_route_is_guarded(self, client):
        """A route added without the router-level dependency should fail this."""
        for method, path in [
            ("get", "/admin/events"),
            ("post", "/admin/events"),
            ("put", f"/admin/events/{'a' * 32}"),
            ("get", "/admin/tips"),
            ("post", "/admin/tips"),
            ("delete", f"/admin/tips/{'a' * 32}"),
            ("post", "/admin/extract"),
            ("get", "/admin/status"),
        ]:
            call = getattr(client, method)
            response = call(path, json={}) if method in {"post", "put"} else call(path)
            assert response.status_code == 401, f"{method.upper()} {path} was not guarded"


class TestCreateEvent:
    def test_creates_one_event(self, admin_client):
        response = admin_client.post("/admin/events", json=event_payload())
        assert response.status_code == 201
        body = response.json()
        assert len(body["created"]) == 1
        assert body["created"][0]["name"] == "Cactus Sessions"

    def test_local_time_is_converted_to_utc(self, admin_client):
        """21:00 Vegas on a PDT date is 04:00 UTC the next day."""
        body = admin_client.post("/admin/events", json=event_payload()).json()
        stored = datetime.fromisoformat(body["created"][0]["start_at"])
        assert stored == START_UTC

    def test_local_time_round_trips_back_unchanged(self, admin_client):
        body = admin_client.post("/admin/events", json=event_payload()).json()
        assert body["created"][0]["starts_at_local"] == START_LOCAL

    def test_created_events_are_not_sample_data(self, admin_client):
        body = admin_client.post("/admin/events", json=event_payload()).json()
        assert body["created"][0]["is_sample"] is False

    def test_end_before_start_is_rejected(self, admin_client):
        payload = event_payload(ends_at_local="2026-08-07T20:00")
        assert admin_client.post("/admin/events", json=payload).status_code == 422

    def test_timezone_aware_input_is_rejected(self, admin_client):
        """The client must send Vegas wall clock, never an offset."""
        payload = event_payload(starts_at_local="2026-08-07T21:00+00:00")
        assert admin_client.post("/admin/events", json=payload).status_code == 422

    def test_unknown_vibe_is_rejected(self, admin_client):
        assert admin_client.post("/admin/events", json=event_payload(vibe="karaoke")).status_code == 422

    def test_unknown_field_is_rejected(self, admin_client):
        payload = event_payload(sneaky="value")
        assert admin_client.post("/admin/events", json=payload).status_code == 422

    def test_unconfigured_r2_warns_but_still_saves(self, admin_client):
        payload = event_payload(image_url="https://example.com/poster.jpg", mirror_image=True)
        response = admin_client.post("/admin/events", json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["image_mirrored"] is False
        assert "R2" in body["image_warning"]
        # The event is live regardless; the image just was not copied.
        assert body["created"][0]["image_url"] == "https://example.com/poster.jpg"


class TestDuplicates:
    def test_second_save_at_the_same_venue_and_time_is_blocked(self, admin_client):
        admin_client.post("/admin/events", json=event_payload())
        response = admin_client.post("/admin/events", json=event_payload())
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["reason"] == "possible_duplicates"
        assert len(detail["collisions"][0]["existing"]) == 1

    def test_force_saves_anyway(self, admin_client):
        admin_client.post("/admin/events", json=event_payload())
        response = admin_client.post("/admin/events?force=true", json=event_payload())
        assert response.status_code == 201

    def test_a_genuinely_different_event_is_not_blocked(self, admin_client):
        admin_client.post("/admin/events", json=event_payload())
        other = event_payload(name="Ladies Night", venue="Little Foxes")
        assert admin_client.post("/admin/events", json=other).status_code == 201

    def test_the_collision_reports_which_night_it_hit(self, admin_client):
        admin_client.post("/admin/events", json=event_payload())
        response = admin_client.post("/admin/events", json=event_payload())
        assert response.json()["detail"]["collisions"][0]["attempted_start_local"] == START_LOCAL


class TestSeries:
    def test_weekly_run_creates_a_row_per_night(self, admin_client):
        payload = event_payload(
            recurrence={"weekdays": ["friday"], "until_local_date": "2026-08-28"}
        )
        body = admin_client.post("/admin/events", json=payload).json()
        assert len(body["created"]) == 4
        assert [item["starts_at_local"][:10] for item in body["created"]] == [
            "2026-08-07",
            "2026-08-14",
            "2026-08-21",
            "2026-08-28",
        ]

    def test_every_night_keeps_the_same_wall_clock_time(self, admin_client):
        payload = event_payload(
            recurrence={"weekdays": ["friday"], "until_local_date": "2026-08-28"}
        )
        body = admin_client.post("/admin/events", json=payload).json()
        assert {item["starts_at_local"][11:] for item in body["created"]} == {"21:00"}

    def test_open_ended_run_is_capped(self, admin_client):
        payload = event_payload(recurrence={"weekdays": ["friday"], "until_local_date": None})
        body = admin_client.post("/admin/events", json=payload).json()
        # settings.max_series_occurrences
        assert len(body["created"]) == 26

    def test_a_recurrence_with_no_dates_is_rejected(self, admin_client):
        payload = event_payload(
            recurrence={"weekdays": ["monday"], "until_local_date": "2026-08-07"}
        )
        response = admin_client.post("/admin/events", json=payload)
        assert response.status_code == 422


class TestListAndEdit:
    def test_search_matches_name_or_venue(self, admin_client):
        admin_client.post("/admin/events", json=event_payload())
        admin_client.post("/admin/events", json=event_payload(name="Other", venue="Little Foxes"))
        assert len(admin_client.get("/admin/events?q=velvet").json()) == 1
        assert len(admin_client.get("/admin/events?q=cactus").json()) == 1

    def test_inactive_events_can_be_excluded(self, admin_client):
        created = admin_client.post("/admin/events", json=event_payload()).json()["created"][0]
        admin_client.post(f"/admin/events/{created['id']}/deactivate")
        assert admin_client.get("/admin/events?include_inactive=false").json() == []

    def test_deactivate_flags_rather_than_deletes(self, admin_client, db):
        created = admin_client.post("/admin/events", json=event_payload()).json()["created"][0]
        admin_client.post(f"/admin/events/{created['id']}/deactivate")
        assert db.get(Event, created["id"]).is_active is False

    def test_replace_updates_every_field(self, admin_client):
        created = admin_client.post("/admin/events", json=event_payload()).json()["created"][0]
        response = admin_client.put(
            f"/admin/events/{created['id']}",
            json=event_payload(name="Renamed", hook="A different hook entirely"),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"

    def test_editing_a_sample_event_makes_it_real(self, admin_client, db):
        """This is how the app's sample-data banner clears itself."""
        from .test_api import add_event

        sample = add_event(db, is_sample=True)
        admin_client.put(f"/admin/events/{sample.id}", json=event_payload())
        db.refresh(sample)
        assert sample.is_sample is False

    def test_replace_rejects_a_recurrence(self, admin_client):
        created = admin_client.post("/admin/events", json=event_payload()).json()["created"][0]
        response = admin_client.put(
            f"/admin/events/{created['id']}",
            json=event_payload(recurrence={"weekdays": ["friday"], "until_local_date": None}),
        )
        assert response.status_code == 422

    def test_unknown_event_is_a_404(self, admin_client):
        assert admin_client.get(f"/admin/events/{'a' * 32}").status_code == 404


class TestTips:
    def test_create_and_list(self, admin_client):
        response = admin_client.post(
            "/admin/tips", json={"vibe": "nightlife", "tip": "Get on the list early.", "priority": 5}
        )
        assert response.status_code == 201
        assert len(admin_client.get("/admin/tips").json()) == 1

    def test_a_tip_targeting_nothing_is_rejected(self, admin_client):
        response = admin_client.post("/admin/tips", json={"tip": "Matches nothing."})
        assert response.status_code == 422

    def test_update_and_delete(self, admin_client):
        created = admin_client.post(
            "/admin/tips", json={"venue": "Neon Cathedral", "tip": "Original."}
        ).json()
        updated = admin_client.put(
            f"/admin/tips/{created['id']}", json={"venue": "Neon Cathedral", "tip": "Revised."}
        )
        assert updated.json()["tip"] == "Revised."
        assert admin_client.delete(f"/admin/tips/{created['id']}").status_code == 204
        assert admin_client.get("/admin/tips").json() == []

    def test_a_new_tip_reaches_the_public_api(self, admin_client, client, db):
        """The whole point of tips living in the database: no redeploy to add one."""
        from .test_api import add_event

        add_event(db, vibe="nightlife")
        admin_client.post("/admin/tips", json={"vibe": "nightlife", "tip": "Guest list closes early."})
        body = client.get("/events", params={"date": "all"}).json()
        assert body["items"][0]["insider_tip"] == "Guest list closes early."


class TestStatus:
    def test_reports_capabilities(self, admin_client):
        body = admin_client.get("/admin/status").json()
        # Both are forced off in conftest so tests never reach the network.
        assert body["extraction_enabled"] is False
        assert body["r2_enabled"] is False


def _fake_result(**overrides) -> ExtractionResult:
    event = ExtractedEvent(
        name="Midnight Mass",
        venue="Neon Cathedral",
        neighborhood=Neighborhood.STRIP,
        starts_at_local="2026-08-07T22:00",
        ends_at_local="2026-08-08T03:00",
        vibe=Vibe.NIGHTLIFE,
        price_tier=PriceTier.PREMIUM,
        price_note="$175 GA",
        hook="The big room, the big lights, the big line",
        description="The flagship Friday night.",
        ticket_url="https://example.com/tickets",
        image_url=None,
    )
    defaults = {
        "found_event": True,
        "event": event,
        "recurrence": RecurrenceHint(repeats=False, weekdays=[], until_local_date=None),
        "uncertain_fields": [],
        "notes": "",
    }
    defaults.update(overrides)
    return ExtractionResult(**defaults)


class TestExtractEndpoint:
    def test_returns_a_draft_the_form_can_load(self, admin_client, monkeypatch):
        monkeypatch.setattr("app.routers.admin.extract_event", lambda **_: _fake_result())
        body = admin_client.post("/admin/extract", json={"url": "https://example.com/e"}).json()
        assert body["found_event"] is True
        assert body["draft"]["name"] == "Midnight Mass"
        assert body["draft"]["starts_at_local"] == "2026-08-07T22:00"
        assert body["draft"]["source_url"] == "https://example.com/e"

    def test_extraction_writes_nothing(self, admin_client, monkeypatch, db):
        monkeypatch.setattr("app.routers.admin.extract_event", lambda **_: _fake_result())
        admin_client.post("/admin/extract", json={"url": "https://example.com/e"})
        assert db.query(Event).count() == 0

    def test_missing_end_time_gets_a_default_duration(self, admin_client, monkeypatch):
        result = _fake_result()
        result.event.ends_at_local = None
        monkeypatch.setattr("app.routers.admin.extract_event", lambda **_: result)
        body = admin_client.post("/admin/extract", json={"url": "https://example.com/e"}).json()
        assert body["draft"]["ends_at_local"] == "2026-08-08T01:00"

    def test_a_page_with_no_event_reports_why(self, admin_client, monkeypatch):
        result = _fake_result(found_event=False, event=None, notes="This is a venue homepage.")
        monkeypatch.setattr("app.routers.admin.extract_event", lambda **_: result)
        body = admin_client.post("/admin/extract", json={"url": "https://example.com/"}).json()
        assert body["found_event"] is False
        assert body["draft"] is None
        assert "homepage" in body["notes"]

    def test_uncertain_fields_reach_the_client(self, admin_client, monkeypatch):
        result = _fake_result(uncertain_fields=["price_tier", "neighborhood"])
        monkeypatch.setattr("app.routers.admin.extract_event", lambda **_: result)
        body = admin_client.post("/admin/extract", json={"url": "https://example.com/e"}).json()
        assert body["uncertain_fields"] == ["price_tier", "neighborhood"]

    def test_recurrence_is_passed_through(self, admin_client, monkeypatch):
        result = _fake_result(
            recurrence=RecurrenceHint(
                repeats=True, weekdays=["friday"], until_local_date="2026-08-28"
            )
        )
        monkeypatch.setattr("app.routers.admin.extract_event", lambda **_: result)
        body = admin_client.post("/admin/extract", json={"url": "https://example.com/e"}).json()
        assert body["recurrence"] == {
            "repeats": True,
            "weekdays": ["friday"],
            "until_local_date": "2026-08-28",
        }

    def test_extraction_failure_is_a_422_with_the_reason(self, admin_client, monkeypatch):
        def explode(**_):
            raise ExtractionError("That page was too long to process.")

        monkeypatch.setattr("app.routers.admin.extract_event", explode)
        response = admin_client.post("/admin/extract", json={"url": "https://example.com/e"})
        assert response.status_code == 422
        assert "too long" in response.json()["detail"]

    def test_both_url_and_text_is_rejected(self, admin_client):
        response = admin_client.post("/admin/extract", json={"url": "https://e.com", "text": "hi"})
        assert response.status_code == 422

    def test_neither_url_nor_text_is_rejected(self, admin_client):
        assert admin_client.post("/admin/extract", json={}).status_code == 422

    def test_unconfigured_key_gives_a_useful_message(self, admin_client):
        """No monkeypatch: the real function runs and finds no API key."""
        response = admin_client.post("/admin/extract", json={"text": "Some pasted flyer text."})
        assert response.status_code == 422
        assert "ANTHROPIC_API_KEY" in response.json()["detail"]
