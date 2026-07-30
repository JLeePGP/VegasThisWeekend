"""Interaction counters.

These cover the two things most likely to go wrong quietly: the upsert overwriting
instead of accumulating, and the public endpoint accepting things it should not.
"""

from __future__ import annotations

from datetime import timedelta

from app.models import StatCounter
from app.stats import summary, vegas_today
from tests.test_api import add_event


def post(client, items):
    return client.post("/interactions", json={"items": items})


class TestRecording:
    def test_records_a_site_wide_metric(self, client, db):
        assert post(client, [{"metric": "share_create"}]).status_code == 202
        row = db.query(StatCounter).one()
        assert (row.metric, row.event_id, row.count) == ("share_create", None, 1)

    def test_records_a_per_event_metric(self, client, db):
        event = add_event(db)
        post(client, [{"metric": "save", "event_id": event.id}])
        row = db.query(StatCounter).one()
        assert (row.metric, row.event_id, row.count) == ("save", event.id, 1)

    def test_repeated_metrics_in_one_batch_are_summed(self, client, db):
        event = add_event(db)
        post(client, [{"metric": "save", "event_id": event.id}] * 5)
        assert db.query(StatCounter).one().count == 5

    def test_a_later_batch_adds_rather_than_overwrites(self, client, db):
        """The upsert must accumulate. Overwriting would silently reset the count on
        every flush, which reads as low traffic rather than as a bug."""
        event = add_event(db)
        post(client, [{"metric": "save", "event_id": event.id}] * 3)
        post(client, [{"metric": "save", "event_id": event.id}] * 4)
        assert db.query(StatCounter).one().count == 7

    def test_site_wide_metric_accumulates_into_one_row(self, client, db):
        """Guards the partial-index design: NULL != NULL, so a plain unique index over
        a nullable column would let every flush insert a fresh row instead."""
        for _ in range(3):
            post(client, [{"metric": "share_create"}])
        rows = db.query(StatCounter).filter(StatCounter.metric == "share_create").all()
        assert len(rows) == 1
        assert rows[0].count == 3

    def test_separate_events_get_separate_counters(self, client, db):
        one = add_event(db, name="One")
        two = add_event(db, name="Two")
        post(
            client,
            [
                {"metric": "save", "event_id": one.id},
                {"metric": "save", "event_id": two.id},
                {"metric": "save", "event_id": two.id},
            ],
        )
        counts = {row.event_id: row.count for row in db.query(StatCounter).all()}
        assert counts == {one.id: 1, two.id: 2}

    def test_records_against_the_vegas_calendar_day(self, client, db):
        post(client, [{"metric": "share_create"}])
        assert db.query(StatCounter).one().day == vegas_today()


class TestRejection:
    def test_unknown_metric_is_rejected(self, client):
        assert post(client, [{"metric": "definitely_not_a_metric"}]).status_code == 422

    def test_empty_batch_is_rejected(self, client):
        assert client.post("/interactions", json={"items": []}).status_code == 422

    def test_oversized_batch_is_rejected(self, client):
        assert post(client, [{"metric": "share_create"}] * 51).status_code == 422

    def test_unknown_event_id_is_dropped_not_fatal(self, client, db):
        """A stale tab can hold an event that has since been pulled. Failing the whole
        batch would lose the other interactions in it for no benefit."""
        event = add_event(db)
        response = post(
            client,
            [
                {"metric": "save", "event_id": "0" * 32},
                {"metric": "save", "event_id": event.id},
            ],
        )
        assert response.status_code == 202
        rows = db.query(StatCounter).all()
        assert len(rows) == 1 and rows[0].event_id == event.id

    def test_malformed_event_id_is_dropped(self, client, db):
        add_event(db)
        response = post(client, [{"metric": "save", "event_id": "../../etc/passwd"}])
        assert response.status_code == 202
        assert db.query(StatCounter).count() == 0

    def test_event_id_on_a_site_wide_metric_is_ignored(self, client, db):
        event = add_event(db)
        post(client, [{"metric": "share_create", "event_id": event.id}])
        assert db.query(StatCounter).one().event_id is None

    def test_the_table_has_nowhere_to_put_a_person(self, client, db):
        """The argument for replacing a third-party script rather than adding to one:
        there is no session, no IP and no user agent, by construction."""
        post(client, [{"metric": "share_create"}])
        columns = {column.name for column in StatCounter.__table__.columns}
        assert columns == {"id", "day", "metric", "event_id", "count"}


class TestSummary:
    def test_totals_group_by_metric(self, client, db):
        event = add_event(db)
        post(
            client,
            [
                {"metric": "save", "event_id": event.id},
                {"metric": "save", "event_id": event.id},
                {"metric": "skip", "event_id": event.id},
                {"metric": "share_create"},
            ],
        )
        assert summary(db)["totals"] == {"save": 2, "skip": 1, "share_create": 1}

    def test_save_rate_is_of_decisions_not_of_impressions(self, client, db):
        """Ranking by raw saves ranks by how long a card sat near the top of the stack.
        Save rate is what says whether people actually wanted it."""
        popular = add_event(db, name="Popular")
        seen_a_lot = add_event(db, name="Seen A Lot")
        post(
            client,
            [{"metric": "save", "event_id": popular.id}] * 3
            + [{"metric": "skip", "event_id": popular.id}]
            + [{"metric": "save", "event_id": seen_a_lot.id}] * 4
            + [{"metric": "skip", "event_id": seen_a_lot.id}] * 16,
        )

        by_name = {e["name"]: e for e in summary(db)["events"]}
        assert by_name["Popular"]["save_rate"] == 0.75
        assert by_name["Seen A Lot"]["save_rate"] == 0.2
        # Raw saves would have ranked the worse event first.
        assert by_name["Seen A Lot"]["metrics"]["save"] > by_name["Popular"]["metrics"]["save"]

    def test_save_rate_is_null_when_nobody_decided(self, client, db):
        event = add_event(db)
        post(client, [{"metric": "detail_open", "event_id": event.id}])
        assert summary(db)["events"][0]["save_rate"] is None

    def test_events_are_ranked_by_saves(self, client, db):
        low = add_event(db, name="Low")
        high = add_event(db, name="High")
        post(
            client,
            [{"metric": "save", "event_id": low.id}]
            + [{"metric": "save", "event_id": high.id}] * 5,
        )
        assert [e["name"] for e in summary(db)["events"]] == ["High", "Low"]

    def test_by_vibe_aggregates_across_events(self, client, db):
        a = add_event(db, name="A", vibe="music")
        b = add_event(db, name="B", vibe="music")
        c = add_event(db, name="C", vibe="shows")
        post(
            client,
            [{"metric": "save", "event_id": a.id}]
            + [{"metric": "save", "event_id": b.id}] * 2
            + [{"metric": "skip", "event_id": c.id}],
        )
        result = summary(db)["by_vibe"]
        assert result["music"]["saves"] == 3
        assert result["shows"]["saves"] == 0
        assert result["shows"]["save_rate"] == 0.0

    def test_window_excludes_older_days(self, client, db):
        event = add_event(db)
        post(client, [{"metric": "save", "event_id": event.id}])
        row = db.query(StatCounter).one()
        row.day = vegas_today() - timedelta(days=40)
        db.commit()
        assert summary(db, days=7)["totals"] == {}
        assert summary(db, days=60)["totals"] == {"save": 1}

    def test_daily_series_is_keyed_by_iso_date(self, client, db):
        post(client, [{"metric": "share_create"}])
        daily = summary(db)["daily"]
        assert list(daily) == [vegas_today().isoformat()]
        assert daily[vegas_today().isoformat()]["share_create"] == 1

    def test_empty_database_is_not_an_error(self, db):
        result = summary(db)
        assert result["totals"] == {} and result["events"] == []


class TestAdminEndpoint:
    def test_requires_the_admin_token(self, client):
        assert client.get("/admin/stats").status_code == 401

    def test_returns_the_summary(self, admin_client, client, db):
        event = add_event(db)
        post(client, [{"metric": "save", "event_id": event.id}])
        body = admin_client.get("/admin/stats").json()
        assert body["totals"]["save"] == 1
        assert body["events"][0]["name"] == event.name

    def test_day_window_is_bounded(self, admin_client):
        assert admin_client.get("/admin/stats", params={"days": 0}).status_code == 422
        assert admin_client.get("/admin/stats", params={"days": 400}).status_code == 422
