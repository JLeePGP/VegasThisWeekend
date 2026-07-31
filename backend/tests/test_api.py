"""Endpoint behaviour.

Date-window maths is covered in test_timewindow.py with an injectable reference clock.
These tests deliberately use `date=all` or an explicit far-future `on=` date so they do
not depend on which day of the week the suite happens to run.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.models import Event, EventTag, InsiderTip, ShareList
from app.timewindow import VEGAS_TZ

FAR_FUTURE = date.today() + timedelta(days=30)


def add_event(db, **overrides) -> Event:
    start = overrides.pop("start", datetime.combine(FAR_FUTURE, time(20), tzinfo=VEGAS_TZ))
    hours = overrides.pop("hours", 3)
    event = Event(
        name=overrides.pop("name", "Test Event"),
        venue=overrides.pop("venue", "Test Venue"),
        neighborhood=overrides.pop("neighborhood", "Downtown"),
        start_at=start,
        end_at=start + timedelta(hours=hours),
        vibe=overrides.pop("vibe", "music"),
        price_tier=overrides.pop("price_tier", "budget"),
        hook=overrides.pop("hook", "A hook."),
        description=overrides.pop("description", "A description."),
        is_active=overrides.pop("is_active", True),
        is_sample=overrides.pop("is_sample", True),
        **overrides,
    )
    db.add(event)
    db.commit()
    return event


class TestListEvents:
    def test_returns_an_event(self, client, db):
        add_event(db, name="Cactus Sessions")
        body = client.get("/events", params={"date": "all"}).json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Cactus Sessions"

    def test_excludes_events_that_have_finished(self, client, db):
        add_event(db, start=datetime.now(VEGAS_TZ) - timedelta(days=3))
        assert client.get("/events", params={"date": "all"}).json()["total"] == 0

    def test_excludes_inactive_events(self, client, db):
        add_event(db, is_active=False)
        assert client.get("/events", params={"date": "all"}).json()["total"] == 0

    def test_orders_by_start_time(self, client, db):
        late = datetime.combine(FAR_FUTURE, time(22), tzinfo=VEGAS_TZ)
        add_event(db, name="Later", start=late)
        add_event(db, name="Earlier", start=late - timedelta(hours=4))
        names = [item["name"] for item in client.get("/events", params={"date": "all"}).json()["items"]]
        assert names == ["Earlier", "Later"]

    def test_filters_by_vibe(self, client, db):
        add_event(db, name="Show", vibe="shows")
        add_event(db, name="Gig", vibe="music")
        body = client.get("/events", params={"date": "all", "vibe": "shows"}).json()
        assert [item["name"] for item in body["items"]] == ["Show"]

    def test_vibe_filter_accepts_several_values(self, client, db):
        add_event(db, name="Show", vibe="shows")
        add_event(db, name="Gig", vibe="music")
        add_event(db, name="Brunch", vibe="food_drink")
        body = client.get("/events?date=all&vibe=shows&vibe=music").json()
        assert body["total"] == 2

    def test_filters_by_price_tier(self, client, db):
        add_event(db, name="Free thing", price_tier="free")
        add_event(db, name="Spendy thing", price_tier="premium")
        body = client.get("/events", params={"date": "all", "price": "free"}).json()
        assert [item["name"] for item in body["items"]] == ["Free thing"]

    def test_explicit_date_selects_that_day_only(self, client, db):
        add_event(db, name="On the day", start=datetime.combine(FAR_FUTURE, time(20), tzinfo=VEGAS_TZ))
        assert client.get("/events", params={"on": FAR_FUTURE.isoformat()}).json()["total"] == 1
        next_day = (FAR_FUTURE + timedelta(days=1)).isoformat()
        assert client.get("/events", params={"on": next_day}).json()["total"] == 0

    def test_late_night_event_files_under_the_day_it_started(self, client, db):
        # 01:00 the morning after is still that night's event.
        after_midnight = datetime.combine(FAR_FUTURE + timedelta(days=1), time(1), tzinfo=VEGAS_TZ)
        add_event(db, name="Late one", start=after_midnight, hours=2)
        assert client.get("/events", params={"on": FAR_FUTURE.isoformat()}).json()["total"] == 1

    def test_rejects_unknown_vibe(self, client):
        assert client.get("/events", params={"vibe": "karaoke"}).status_code == 422

    def test_rejects_unknown_price_tier(self, client):
        assert client.get("/events", params={"price": "cheap"}).status_code == 422

    def test_rejects_malformed_date(self, client):
        assert client.get("/events", params={"on": "next friday"}).status_code == 422


class TestVideoLeadsTheFeed:
    """The first card is the app's first impression, so a video leads when one exists.

    The rotation is by listing day rather than random, and the tests below pin the two
    reasons why: a shared edge cache serves every visitor the same stored copy, and offset
    pagination against a reshuffling order would duplicate and drop cards on scroll.
    """

    def names(self, client, **params):
        query = {"date": "all", **params}
        return [item["name"] for item in client.get("/events", params=query).json()["items"]]

    def test_a_video_event_leads_even_when_it_starts_later(self, client, db):
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        add_event(db, name="Photo only", start=early)
        add_event(db, name="Has video", start=early + timedelta(hours=4),
                  video_url="https://media.vegasthisweekend.com/video/a.mp4")
        assert self.names(client)[0] == "Has video"

    def test_the_rest_of_the_feed_stays_chronological(self, client, db):
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        add_event(db, name="Second", start=early + timedelta(hours=1))
        add_event(db, name="Third", start=early + timedelta(hours=2))
        add_event(db, name="Leads", start=early + timedelta(hours=9),
                  video_url="https://media.vegasthisweekend.com/video/a.mp4")
        assert self.names(client) == ["Leads", "Second", "Third"]

    def test_order_is_untouched_when_nothing_has_video(self, client, db):
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        add_event(db, name="Later", start=early + timedelta(hours=4))
        add_event(db, name="Earlier", start=early)
        assert self.names(client) == ["Earlier", "Later"]

    def test_an_empty_video_url_does_not_count_as_video(self, client, db):
        """A blank string is what an emptied form field stores, and it plays nothing."""
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        add_event(db, name="Later blank", start=early + timedelta(hours=4), video_url="")
        add_event(db, name="Earlier", start=early)
        assert self.names(client) == ["Earlier", "Later blank"]

    def test_the_lead_comes_from_the_filtered_window_only(self, client, db):
        """Promoting a video event the visitor's filter excludes would either leak it in
        or promote nothing — both wrong. The pick runs against the same conditions."""
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        add_event(db, name="Music no video", start=early, vibe="music")
        add_event(db, name="Show with video", start=early + timedelta(hours=2), vibe="shows",
                  video_url="https://media.vegasthisweekend.com/video/a.mp4")
        assert self.names(client, vibe="music") == ["Music no video"]

    def test_paging_never_repeats_or_drops_the_promoted_event(self, client, db):
        """The promotion lives in the ORDER BY for exactly this reason — moving a row
        after the query would serve it again on page 2."""
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        for index in range(4):
            add_event(db, name=f"Event {index}", start=early + timedelta(hours=index))
        add_event(db, name="Leads", start=early + timedelta(hours=9),
                  video_url="https://media.vegasthisweekend.com/video/a.mp4")

        seen = []
        for offset in range(5):
            page = client.get("/events", params={"date": "all", "limit": 1, "offset": offset})
            seen += [item["name"] for item in page.json()["items"]]
        assert seen[0] == "Leads"
        assert len(seen) == len(set(seen)) == 5

    def test_the_lead_is_stable_within_a_day(self, client, db):
        """Two requests a second apart must agree, or paging through would reorder."""
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        for index in range(3):
            add_event(db, name=f"Video {index}", start=early + timedelta(hours=index),
                      video_url=f"https://media.vegasthisweekend.com/video/{index}.mp4")
        assert self.names(client)[0] == self.names(client)[0]

    def test_which_video_leads_rotates_with_the_day(self, client, db, monkeypatch):
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        for index in range(2):
            add_event(db, name=f"Video {index}", start=early + timedelta(hours=index),
                      video_url=f"https://media.vegasthisweekend.com/video/{index}.mp4")

        def on_day(moment):
            monkeypatch.setattr("app.routers.events.now_vegas", lambda: moment)
            return self.names(client)[0]

        noon = datetime.combine(FAR_FUTURE - timedelta(days=7), time(12), tzinfo=VEGAS_TZ)
        assert on_day(noon) != on_day(noon + timedelta(days=1))

    def test_the_rollover_decides_the_day_not_midnight(self, client, db, monkeypatch):
        """4am belongs to the night before, so the lead must not change under someone
        still scrolling at closing time."""
        early = datetime.combine(FAR_FUTURE, time(18), tzinfo=VEGAS_TZ)
        for index in range(2):
            add_event(db, name=f"Video {index}", start=early + timedelta(hours=index),
                      video_url=f"https://media.vegasthisweekend.com/video/{index}.mp4")

        def at(moment):
            monkeypatch.setattr("app.routers.events.now_vegas", lambda: moment)
            return self.names(client)[0]

        day = FAR_FUTURE - timedelta(days=7)
        before_midnight = datetime.combine(day, time(23), tzinfo=VEGAS_TZ)
        after_midnight = datetime.combine(day + timedelta(days=1), time(4), tzinfo=VEGAS_TZ)
        assert at(before_midnight) == at(after_midnight)


class TestPagination:
    def test_caps_the_page_size(self, client):
        assert client.get("/events", params={"limit": 21}).status_code == 422

    def test_pages_through_results(self, client, db):
        base = datetime.combine(FAR_FUTURE, time(9), tzinfo=VEGAS_TZ)
        for index in range(25):
            add_event(db, name=f"Event {index:02d}", start=base + timedelta(minutes=index * 10), hours=1)

        first = client.get("/events", params={"date": "all", "limit": 20}).json()
        assert (first["total"], len(first["items"]), first["has_more"]) == (25, 20, True)

        second = client.get("/events", params={"date": "all", "limit": 20, "offset": 20}).json()
        assert (len(second["items"]), second["has_more"]) == (5, False)

        overlap = {item["id"] for item in first["items"]} & {item["id"] for item in second["items"]}
        assert overlap == set()


class TestSampleDataFlag:
    def test_true_while_placeholder_events_exist(self, client, db):
        add_event(db, is_sample=True)
        assert client.get("/events", params={"date": "all"}).json()["sample_data"] is True

    def test_false_once_events_are_real(self, client, db):
        add_event(db, is_sample=False)
        assert client.get("/events", params={"date": "all"}).json()["sample_data"] is False


class TestInsiderTips:
    def test_matches_on_vibe(self, client, db):
        add_event(db, vibe="nightlife")
        db.add(InsiderTip(vibe="nightlife", tip="Get on the list early."))
        db.commit()
        body = client.get("/events", params={"date": "all"}).json()
        assert body["items"][0]["insider_tip"] == "Get on the list early."

    def test_venue_match_beats_vibe_match(self, client, db):
        add_event(db, venue="Neon Cathedral", vibe="nightlife")
        db.add_all(
            [
                InsiderTip(vibe="nightlife", tip="Generic advice."),
                InsiderTip(venue="Neon Cathedral", tip="Specific advice."),
            ]
        )
        db.commit()
        body = client.get("/events", params={"date": "all"}).json()
        assert body["items"][0]["insider_tip"] == "Specific advice."

    def test_venue_matching_ignores_case_and_padding(self, client, db):
        add_event(db, venue="Neon Cathedral")
        db.add(InsiderTip(venue="  neon cathedral ", tip="Still matches."))
        db.commit()
        body = client.get("/events", params={"date": "all"}).json()
        assert body["items"][0]["insider_tip"] == "Still matches."

    def test_inactive_tips_are_ignored(self, client, db):
        add_event(db, vibe="nightlife")
        db.add(InsiderTip(vibe="nightlife", tip="Retired advice.", is_active=False))
        db.commit()
        body = client.get("/events", params={"date": "all"}).json()
        assert body["items"][0]["insider_tip"] is None

    def test_absent_when_nothing_matches(self, client, db):
        add_event(db, vibe="outdoors")
        db.add(InsiderTip(vibe="nightlife", tip="Unrelated."))
        db.commit()
        body = client.get("/events", params={"date": "all"}).json()
        assert body["items"][0]["insider_tip"] is None


class TestGetEvent:
    def test_returns_the_event(self, client, db):
        event = add_event(db, name="Midnight Mass")
        body = client.get(f"/events/{event.id}").json()
        assert body["name"] == "Midnight Mass"

    def test_unknown_id_is_a_404(self, client):
        assert client.get(f"/events/{'a' * 32}").status_code == 404

    def test_inactive_event_is_a_404(self, client, db):
        event = add_event(db, is_active=False)
        assert client.get(f"/events/{event.id}").status_code == 404

    def test_malformed_id_is_rejected(self, client):
        assert client.get("/events/not-an-id").status_code == 422


class TestEdgeCaching:
    """The public catalog is identical for every visitor, so a shared cache may hold it.

    These assert the header is present where it is safe and — more importantly — absent
    everywhere it is not. A Cache-Control that leaks onto a per-visitor or authenticated
    response means the edge serving one person's response to another, which is the worst
    class of bug this app could have.
    """

    def test_the_listing_is_cacheable_by_shared_caches(self, client, db):
        add_event(db)
        headers = client.get("/events").headers
        assert "s-maxage=60" in headers["cache-control"]
        assert "stale-while-revalidate" in headers["cache-control"]

    def test_the_listing_varies_on_origin(self, client, db):
        """CORS puts the requesting origin in the response, so an edge that ignored this
        could hand a response built for one origin to another."""
        add_event(db)
        assert client.get("/events").headers["vary"] == "Origin"

    def test_a_single_event_is_cacheable(self, client, db):
        event = add_event(db)
        assert "s-maxage=60" in client.get(f"/events/{event.id}").headers["cache-control"]

    def test_a_share_list_is_not_cacheable(self, client, db):
        """A share link is one person's saved events. It must never sit in a shared
        cache, and it must never be handed to whoever asks next."""
        event = add_event(db)
        token = client.post("/share", json={"event_ids": [event.id]}).json()["token"]
        assert "s-maxage" not in client.get(f"/share/{token}").headers.get("cache-control", "")

    def test_admin_responses_are_not_cacheable(self, admin_client, db):
        add_event(db)
        assert "s-maxage" not in admin_client.get("/admin/events").headers.get(
            "cache-control", ""
        )


class TestCreateShare:
    def test_round_trips_and_preserves_order(self, client, db):
        first = add_event(db, name="First")
        second = add_event(db, name="Second")
        third = add_event(db, name="Third")

        ordered = [third.id, first.id, second.id]
        created = client.post("/share", json={"event_ids": ordered})
        assert created.status_code == 201

        token = created.json()["token"]
        assert created.json()["path"] == f"/s/{token}"

        fetched = client.get(f"/share/{token}").json()
        assert [item["name"] for item in fetched["events"]] == ["Third", "First", "Second"]

    def test_drops_ids_that_no_longer_exist(self, client, db):
        event = add_event(db, name="Still here")
        payload = {"event_ids": [event.id, "b" * 32]}
        token = client.post("/share", json=payload).json()["token"]
        fetched = client.get(f"/share/{token}").json()
        assert [item["name"] for item in fetched["events"]] == ["Still here"]

    def test_deduplicates_ids(self, client, db):
        event = add_event(db)
        token = client.post("/share", json={"event_ids": [event.id, event.id]}).json()["token"]
        assert len(client.get(f"/share/{token}").json()["events"]) == 1

    def test_rejects_a_list_of_only_unknown_ids(self, client):
        assert client.post("/share", json={"event_ids": ["c" * 32]}).status_code == 400

    def test_rejects_an_empty_list(self, client):
        assert client.post("/share", json={"event_ids": []}).status_code == 422

    def test_rejects_malformed_ids(self, client):
        assert client.post("/share", json={"event_ids": ["../../etc/passwd"]}).status_code == 422

    def test_enforces_the_twenty_event_cap(self, client, db):
        events = [add_event(db, name=f"Event {index}") for index in range(21)]
        response = client.post("/share", json={"event_ids": [event.id for event in events]})
        assert response.status_code == 400
        assert "20" in response.json()["detail"]

    def test_accepts_exactly_twenty(self, client, db):
        events = [add_event(db, name=f"Event {index}") for index in range(20)]
        response = client.post("/share", json={"event_ids": [event.id for event in events]})
        assert response.status_code == 201


class TestGetShare:
    def test_unknown_token_is_a_404(self, client):
        assert client.get(f"/share/{'d' * 32}").status_code == 404

    def test_malformed_token_is_rejected(self, client):
        assert client.get("/share/nope").status_code == 422

    def test_expired_list_is_a_404(self, client, db):
        event = add_event(db)
        expired = ShareList(
            event_ids=[event.id],
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(expired)
        db.commit()
        assert client.get(f"/share/{expired.token}").status_code == 404

    def test_expiry_is_thirty_days_out(self, client, db):
        event = add_event(db)
        body = client.post("/share", json={"event_ids": [event.id]}).json()
        expires = datetime.fromisoformat(body["expires_at"])
        assert timedelta(days=29) < expires - datetime.now(timezone.utc) <= timedelta(days=30)

    def test_still_shows_an_event_that_has_since_passed(self, client, db):
        """A recipient should see the list that was actually sent, not a filtered one."""
        event = add_event(db, name="Already over")
        token = client.post("/share", json={"event_ids": [event.id]}).json()["token"]

        event.end_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

        fetched = client.get(f"/share/{token}").json()
        assert [item["name"] for item in fetched["events"]] == ["Already over"]


class TestHealth:
    def test_reports_ok(self, client):
        assert client.get("/health").json()["status"] == "ok"


class TestCategories:
    """Multiple categories per event, and the primary/extra split."""

    def test_extra_tag_makes_an_event_appear_under_both_categories(self, client, db):
        yoga = add_event(db, name="Yoga Networking", vibe="fitness")
        yoga.tags = [EventTag(tag="outdoors")]
        db.commit()

        for wanted in ("fitness", "outdoors"):
            body = client.get("/events", params={"date": "all", "vibe": wanted}).json()
            assert [item["name"] for item in body["items"]] == ["Yoga Networking"], wanted

    def test_event_with_no_tag_rows_still_matches_its_own_vibe(self, client, db):
        """Regression guard.

        An earlier design stored the primary vibe in the tag table and filtered on that
        table alone, so an event saved without tag rows vanished from its own category.
        Nothing at the database level enforced it. Filtering now tests the column too,
        which makes the tag table incapable of hiding anything.
        """
        add_event(db, name="Untagged Gig", vibe="music")
        body = client.get("/events", params={"date": "all", "vibe": "music"}).json()
        assert [item["name"] for item in body["items"]] == ["Untagged Gig"]

    def test_tags_lists_the_primary_vibe_first(self, client, db):
        event = add_event(db, vibe="fitness")
        event.tags = [EventTag(tag="outdoors"), EventTag(tag="local")]
        db.commit()

        item = client.get("/events", params={"date": "all"}).json()["items"][0]
        assert item["tags"][0] == "fitness"
        assert set(item["tags"]) == {"fitness", "outdoors", "local"}

    def test_untagged_event_still_reports_its_own_vibe_in_tags(self, client, db):
        add_event(db, vibe="shows")
        item = client.get("/events", params={"date": "all"}).json()["items"][0]
        assert item["tags"] == ["shows"]

    def test_fitness_is_an_accepted_filter_value(self, client, db):
        add_event(db, name="Sunrise Class", vibe="fitness")
        body = client.get("/events", params={"date": "all", "vibe": "fitness"}).json()
        assert [item["name"] for item in body["items"]] == ["Sunrise Class"]

    def test_a_tag_does_not_change_the_primary_vibe(self, client, db):
        event = add_event(db, vibe="fitness")
        event.tags = [EventTag(tag="outdoors")]
        db.commit()
        item = client.get("/events", params={"date": "all"}).json()["items"][0]
        # The card's colours key off this, so it must stay the one the admin chose.
        assert item["vibe"] == "fitness"


class TestAlcoholFree:
    """Sober is an attribute, not a category — the difference is the AND below."""

    def test_filter_excludes_events_that_are_not_alcohol_free(self, client, db):
        add_event(db, name="Dry Night", alcohol_free=True)
        add_event(db, name="Wet Night", alcohol_free=False)
        body = client.get("/events", params={"date": "all", "alcohol_free": "true"}).json()
        assert [item["name"] for item in body["items"]] == ["Dry Night"]

    def test_omitting_the_filter_returns_everything(self, client, db):
        add_event(db, name="Dry Night", alcohol_free=True)
        add_event(db, name="Wet Night", alcohol_free=False)
        assert client.get("/events", params={"date": "all"}).json()["total"] == 2

    def test_composes_with_vibe_using_and_not_or(self, client, db):
        """The reason alcohol-free is not simply another vibe.

        Vibe values combine with OR. If "sober" were one of them, asking for nightlife
        plus sober would return every nightlife event *including the bars*, plus every
        sober event of any kind — and sober nightlife, the one thing the person wants,
        would be the single result the filter could not express.
        """
        add_event(db, name="Sober Rave", vibe="nightlife", alcohol_free=True)
        add_event(db, name="Bar Night", vibe="nightlife", alcohol_free=False)
        add_event(db, name="Dry Yoga", vibe="fitness", alcohol_free=True)

        body = client.get(
            "/events", params={"date": "all", "vibe": "nightlife", "alcohol_free": "true"}
        ).json()
        assert [item["name"] for item in body["items"]] == ["Sober Rave"]

    def test_defaults_to_false_on_events_that_never_set_it(self, client, db):
        add_event(db, name="Legacy Event")
        item = client.get("/events", params={"date": "all"}).json()["items"][0]
        assert item["alcohol_free"] is False


class TestPublicFieldExposure:
    def test_source_url_is_returned(self, client, db):
        """It was stored and admin-editable from the start but never serialised, so the
        client's "Website" link had nothing to render and silently never appeared."""
        add_event(db, source_url="https://example.com/event")
        item = client.get("/events", params={"date": "all"}).json()["items"][0]
        assert item["source_url"] == "https://example.com/event"

    def test_address_is_returned(self, client, db):
        add_event(db, address="123 Fremont St, Las Vegas, NV")
        item = client.get("/events", params={"date": "all"}).json()["items"][0]
        assert item["address"] == "123 Fremont St, Las Vegas, NV"

    def test_address_is_null_on_events_that_predate_the_column(self, client, db):
        add_event(db)
        item = client.get("/events", params={"date": "all"}).json()["items"][0]
        assert item["address"] is None

    def test_single_event_endpoint_exposes_them_too(self, client, db):
        event = add_event(db, source_url="https://example.com/e", address="1 Main St")
        item = client.get(f"/events/{event.id}").json()
        assert item["source_url"] == "https://example.com/e"
        assert item["address"] == "1 Main St"
