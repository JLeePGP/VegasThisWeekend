"""Editing a residency as a series rather than night by night.

The failure this file mostly exists to prevent: a series edit that copies the start
timestamp across every night, collapsing a twenty-six night run onto one date. It is the
obvious implementation, it looks correct in a single-night test, and there is no undo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Event
from app.timewindow import VEGAS_TZ
from tests.test_admin import END_LOCAL, START_LOCAL, event_payload


def create_series(admin_client, weekdays=("friday",), until="2026-08-28", **overrides):
    """Four Friday nights: 7, 14, 21, 28 August 2026."""
    payload = event_payload(
        recurrence={"weekdays": list(weekdays), "until_local_date": until}, **overrides
    )
    response = admin_client.post("/admin/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["created"]


def local_starts(db, name="Cactus Sessions"):
    rows = db.scalars(
        select(Event).where(Event.name == name).order_by(Event.start_at.asc())
    ).all()
    return [row.start_at.astimezone(VEGAS_TZ).strftime("%Y-%m-%d %H:%M") for row in rows]


class TestSeriesIdentity:
    def test_every_night_of_a_run_shares_one_id(self, admin_client):
        created = create_series(admin_client)
        assert len(created) == 4
        ids = {night["series_id"] for night in created}
        assert len(ids) == 1 and ids != {None}

    def test_a_one_off_gets_no_series_id(self, admin_client):
        response = admin_client.post("/admin/events", json=event_payload())
        assert response.json()["created"][0]["series_id"] is None

    def test_a_recurrence_that_produced_one_date_is_not_a_series(self, admin_client):
        """Otherwise the panel offers "this and later nights" over an audience of one."""
        created = create_series(admin_client, until="2026-08-07")
        assert len(created) == 1
        assert created[0]["series_id"] is None

    def test_two_separate_runs_do_not_share_an_id(self, admin_client):
        first = create_series(admin_client)
        second = create_series(admin_client, weekdays=("saturday",), until="2026-08-29")
        assert first[0]["series_id"] != second[0]["series_id"]


class TestEditingOneNight:
    def test_the_default_scope_leaves_the_others_alone(self, admin_client, db):
        created = create_series(admin_client)
        admin_client.put(
            f"/admin/events/{created[0]['id']}",
            json=event_payload(name="Renamed One Night"),
        )
        names = db.scalars(select(Event.name).order_by(Event.start_at.asc())).all()
        assert names == [
            "Renamed One Night",
            "Cactus Sessions",
            "Cactus Sessions",
            "Cactus Sessions",
        ]

    def test_the_response_says_it_reached_one_night(self, admin_client):
        created = create_series(admin_client)
        response = admin_client.put(
            f"/admin/events/{created[0]['id']}", json=event_payload(name="Just this one")
        )
        assert response.json()["applied_to"] == 1


class TestEditingTheSeries:
    def test_later_nights_take_the_new_details(self, admin_client, db):
        created = create_series(admin_client)
        response = admin_client.put(
            f"/admin/events/{created[0]['id']}?scope=series",
            json=event_payload(name="Cactus Sessions: Late Edition", price_tier="premium"),
        )
        assert response.status_code == 200
        assert response.json()["applied_to"] == 4

        rows = db.scalars(select(Event)).all()
        assert {row.name for row in rows} == {"Cactus Sessions: Late Edition"}
        assert {row.price_tier for row in rows} == {"premium"}

    def test_each_night_keeps_its_own_date(self, admin_client, db):
        """The one that matters. Copying start_at across would put all four nights on
        7 August and there would be no way back."""
        create_series(admin_client)
        before = local_starts(db)
        assert before == [
            "2026-08-07 21:00",
            "2026-08-14 21:00",
            "2026-08-21 21:00",
            "2026-08-28 21:00",
        ]

        first_id = db.scalars(
            select(Event.id).order_by(Event.start_at.asc())
        ).first()
        admin_client.put(
            f"/admin/events/{first_id}?scope=series", json=event_payload(name="Cactus Sessions")
        )

        assert local_starts(db) == before

    def test_a_new_time_of_day_moves_every_later_night(self, admin_client, db):
        create_series(admin_client)
        first_id = db.scalars(select(Event.id).order_by(Event.start_at.asc())).first()

        # 9pm-1am becomes 8pm-11pm, on the same four dates.
        admin_client.put(
            f"/admin/events/{first_id}?scope=series",
            json=event_payload(
                starts_at_local="2026-08-07T20:00", ends_at_local="2026-08-07T23:00"
            ),
        )

        assert local_starts(db) == [
            "2026-08-07 20:00",
            "2026-08-14 20:00",
            "2026-08-21 20:00",
            "2026-08-28 20:00",
        ]
        durations = {
            row.end_at - row.start_at for row in db.scalars(select(Event)).all()
        }
        assert durations == {timedelta(hours=3)}

    def test_moving_one_night_to_another_date_does_not_move_the_rest(
        self, admin_client, db
    ):
        """A date change is about that night. A time change is about the residency."""
        create_series(admin_client)
        first_id = db.scalars(select(Event.id).order_by(Event.start_at.asc())).first()

        admin_client.put(
            f"/admin/events/{first_id}?scope=series",
            json=event_payload(
                starts_at_local="2026-08-08T21:00", ends_at_local="2026-08-09T01:00"
            ),
        )

        assert local_starts(db) == [
            "2026-08-08 21:00",
            "2026-08-14 21:00",
            "2026-08-21 21:00",
            "2026-08-28 21:00",
        ]

    def test_a_night_already_past_is_never_rewritten(self, admin_client, db):
        """History is what people were told. A series edit is "from here on"."""
        create_series(admin_client)
        rows = db.scalars(select(Event).order_by(Event.start_at.asc())).all()
        gone = rows[1]
        gone.start_at = datetime.now(timezone.utc) - timedelta(days=3)
        gone.end_at = gone.start_at + timedelta(hours=4)
        db.commit()
        past_id, past_start = gone.id, gone.start_at

        admin_client.put(
            f"/admin/events/{rows[0].id}?scope=series",
            json=event_payload(name="Changed After The Fact"),
        )

        untouched = db.get(Event, past_id)
        assert untouched.name == "Cactus Sessions"
        assert untouched.start_at == past_start

    def test_series_scope_on_a_one_off_is_refused(self, admin_client):
        created = admin_client.post("/admin/events", json=event_payload()).json()["created"]
        response = admin_client.put(
            f"/admin/events/{created[0]['id']}?scope=series", json=event_payload()
        )
        assert response.status_code == 422
        assert "not part of a series" in response.json()["detail"]


class TestDeactivatingTheSeries:
    def test_one_call_pulls_every_later_night(self, admin_client, db):
        created = create_series(admin_client)
        admin_client.post(f"/admin/events/{created[0]['id']}/deactivate?scope=series")
        assert {row.is_active for row in db.scalars(select(Event)).all()} == {False}

    def test_the_default_pulls_only_that_night(self, admin_client, db):
        created = create_series(admin_client)
        admin_client.post(f"/admin/events/{created[0]['id']}/deactivate")
        active = [row.is_active for row in db.scalars(select(Event).order_by(Event.start_at)).all()]
        assert active == [False, True, True, True]


class TestLinkingOlderRows:
    """Series ids arrived after the events did. Production has a three-night run with
    none, which is the case this exists for."""

    def make_unlinked_pair(self, admin_client):
        first = admin_client.post("/admin/events", json=event_payload()).json()["created"][0]
        second = admin_client.post(
            "/admin/events",
            json=event_payload(
                starts_at_local="2026-08-14T21:00", ends_at_local="2026-08-15T01:00"
            ),
        ).json()["created"][0]
        return first, second

    def test_matching_nights_are_offered_as_candidates(self, admin_client):
        first, second = self.make_unlinked_pair(admin_client)
        payload = admin_client.get(f"/admin/events/{first['id']}/series").json()
        assert payload["series_id"] is None
        assert [night["id"] for night in payload["candidates"]] == [second["id"]]

    def test_a_different_venue_is_not_a_candidate(self, admin_client):
        first, _ = self.make_unlinked_pair(admin_client)
        admin_client.post(
            "/admin/events", json=event_payload(venue="Somewhere Else")
        )
        payload = admin_client.get(f"/admin/events/{first['id']}/series").json()
        assert all("Somewhere Else" not in night["id"] for night in payload["candidates"])
        assert len(payload["candidates"]) == 1

    def test_linking_groups_them(self, admin_client, db):
        first, second = self.make_unlinked_pair(admin_client)
        response = admin_client.post(
            f"/admin/events/{first['id']}/series", json={"event_ids": [second["id"]]}
        )
        assert response.status_code == 200
        assert response.json()["series_id"] is not None

        ids = {row.series_id for row in db.scalars(select(Event)).all()}
        assert len(ids) == 1 and ids != {None}

    def test_a_linked_run_can_then_be_edited_as_one(self, admin_client, db):
        first, second = self.make_unlinked_pair(admin_client)
        admin_client.post(
            f"/admin/events/{first['id']}/series", json={"event_ids": [second["id"]]}
        )
        response = admin_client.put(
            f"/admin/events/{first['id']}?scope=series",
            json=event_payload(name="Now A Residency"),
        )
        assert response.json()["applied_to"] == 2
        assert {row.name for row in db.scalars(select(Event)).all()} == {"Now A Residency"}

    def test_linking_into_an_existing_run_keeps_its_id(self, admin_client, db):
        created = create_series(admin_client)
        existing_id = created[0]["series_id"]
        stray = admin_client.post(
            "/admin/events",
            json=event_payload(
                starts_at_local="2026-09-04T21:00", ends_at_local="2026-09-05T01:00"
            ),
        ).json()["created"][0]

        admin_client.post(
            f"/admin/events/{stray['id']}/series", json={"event_ids": [created[0]["id"]]}
        )
        assert db.get(Event, stray["id"]).series_id == existing_id

    def test_merging_two_different_series_is_refused(self, admin_client):
        first = create_series(admin_client)
        second = create_series(admin_client, weekdays=("saturday",), until="2026-08-29")
        response = admin_client.post(
            f"/admin/events/{first[0]['id']}/series",
            json={"event_ids": [second[0]["id"]]},
        )
        assert response.status_code == 409

    def test_an_unknown_id_is_refused_rather_than_partly_linked(self, admin_client, db):
        first, second = self.make_unlinked_pair(admin_client)
        response = admin_client.post(
            f"/admin/events/{first['id']}/series",
            json={"event_ids": [second["id"], "f" * 32]},
        )
        assert response.status_code == 404
        assert {row.series_id for row in db.scalars(select(Event)).all()} == {None}
