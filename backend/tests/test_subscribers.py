"""Newsletter signup.

The privacy tests here are not decoration. This is the only table in the project holding
personal data, and the two ways it could quietly become something worse are storing more
than the address and letting the response reveal who is already on the list.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import select

from app.models import Subscriber
from app.timewindow import VEGAS_TZ


def signup(client, email="someone@example.com", source="list_end"):
    return client.post("/subscribers", json={"email": email, "source": source})


class TestSigningUp:
    def test_a_valid_address_is_accepted(self, client, db):
        assert signup(client).status_code == 202
        assert db.scalars(select(Subscriber.email)).all() == ["someone@example.com"]

    def test_the_source_is_recorded(self, client, db):
        signup(client, source="saved")
        assert db.scalar(select(Subscriber.source)) == "saved"

    def test_both_surfaces_are_accepted(self, client):
        assert signup(client, email="a@example.com", source="list_end").status_code == 202
        assert signup(client, email="b@example.com", source="saved").status_code == 202

    def test_an_unknown_source_is_rejected(self, client, db):
        assert signup(client, source="somewhere_else").status_code == 422
        assert db.scalars(select(Subscriber)).all() == []

    def test_junk_is_not_an_address(self, client, db):
        for junk in ("not-an-email", "@example.com", "someone@", "", "someone@example"):
            assert signup(client, email=junk).status_code == 422, junk
        assert db.scalars(select(Subscriber)).all() == []

    def test_an_address_too_long_to_deliver_to_is_rejected(self, client):
        assert signup(client, email=f"{'a' * 250}@example.com").status_code == 422


class TestSigningUpTwice:
    """Someone who does not remember subscribing will subscribe again. That must be a
    no-op, and must look identical to a first-time signup from the outside."""

    def test_the_second_attempt_still_succeeds(self, client):
        assert signup(client).status_code == 202
        assert signup(client).status_code == 202

    def test_no_duplicate_row_is_created(self, client, db):
        signup(client)
        signup(client)
        assert len(db.scalars(select(Subscriber)).all()) == 1

    def test_case_and_whitespace_do_not_create_a_second_row(self, client, db):
        signup(client, email="Someone@Example.com")
        signup(client, email="  someone@example.com  ")
        rows = db.scalars(select(Subscriber.email)).all()
        assert rows == ["someone@example.com"]

    def test_the_response_does_not_reveal_who_is_already_subscribed(self, client):
        """Otherwise the endpoint answers "is this person on the list" for any address."""
        first = signup(client)
        second = signup(client)
        assert (first.status_code, first.json()) == (second.status_code, second.json())


class TestTheAdminList:
    """How John actually gets the addresses out. The `since` window is the whole reason
    a second export cannot re-add someone who unsubscribed with the provider."""

    def test_the_list_is_returned_in_full(self, client, admin_client):
        for index in range(3):
            signup(client, email=f"person{index}@example.com")

        payload = admin_client.get("/admin/subscribers").json()
        assert payload["total"] == 3
        assert len(payload["items"]) == 3
        assert {item["email"] for item in payload["items"]} == {
            "person0@example.com",
            "person1@example.com",
            "person2@example.com",
        }

    def test_newest_first(self, client, admin_client, db):
        signup(client, email="first@example.com")
        signup(client, email="second@example.com")

        # Ordering is by stored timestamp, and two signups in the same test can land in
        # the same microsecond — so the first one is aged deliberately.
        row = db.scalars(select(Subscriber).where(Subscriber.email == "first@example.com")).one()
        row.created_at = row.created_at - timedelta(hours=1)
        db.commit()

        emails = [item["email"] for item in admin_client.get("/admin/subscribers").json()["items"]]
        assert emails == ["second@example.com", "first@example.com"]

    def test_since_excludes_earlier_signups(self, client, admin_client, db):
        signup(client, email="old@example.com")
        signup(client, email="new@example.com")

        row = db.scalars(select(Subscriber).where(Subscriber.email == "old@example.com")).one()
        row.created_at = row.created_at - timedelta(days=10)
        db.commit()

        today = datetime.now(VEGAS_TZ).date()
        payload = admin_client.get(
            "/admin/subscribers", params={"since": today.isoformat()}
        ).json()
        assert payload["total"] == 1
        assert payload["items"][0]["email"] == "new@example.com"

    def test_since_counts_from_vegas_midnight_not_utc(self, client, admin_client, db):
        """A signup at 6pm Vegas is stored as the next day in UTC. Filtering on the UTC
        day would drop it from an export made the same evening."""
        signup(client, email="evening@example.com")

        today = datetime.now(VEGAS_TZ).date()
        row = db.scalars(
            select(Subscriber).where(Subscriber.email == "evening@example.com")
        ).one()
        row.created_at = datetime.combine(today, time(18, 0), tzinfo=VEGAS_TZ)
        db.commit()

        payload = admin_client.get(
            "/admin/subscribers", params={"since": today.isoformat()}
        ).json()
        assert payload["total"] == 1

    def test_an_address_can_be_removed(self, client, admin_client, db):
        """Typos, hard bounces and the deploy probe that verified the endpoint."""
        signup(client, email="typo@exmaple.com")
        row = db.scalars(select(Subscriber)).one()

        assert admin_client.delete(f"/admin/subscribers/{row.id}").status_code == 204
        assert db.scalars(select(Subscriber)).all() == []

    def test_removing_an_unknown_id_is_a_404(self, admin_client):
        assert admin_client.delete(f"/admin/subscribers/{'a' * 32}").status_code == 404

    def test_a_malformed_id_is_rejected_before_the_query(self, admin_client):
        assert admin_client.delete("/admin/subscribers/../../etc/passwd").status_code == 404

    def test_removing_one_lets_that_person_sign_up_again(self, client, admin_client, db):
        """A delete is a real delete, so nothing shadows a returning subscriber."""
        signup(client)
        row = db.scalars(select(Subscriber)).one()
        admin_client.delete(f"/admin/subscribers/{row.id}")

        signup(client)
        assert len(db.scalars(select(Subscriber)).all()) == 1


class TestNothingElseIsStored:
    def test_only_the_address_source_and_time_are_kept(self, client, db):
        signup(client)
        row = db.scalars(select(Subscriber)).one()
        # Named explicitly rather than counted: a future column holding an IP or a user
        # agent should fail here loudly, not slip past a length check.
        stored = {column.name for column in row.__table__.columns}
        assert stored == {"id", "email", "source", "created_at"}

    def test_extra_fields_in_the_request_are_ignored(self, client, db):
        client.post(
            "/subscribers",
            json={
                "email": "someone@example.com",
                "source": "list_end",
                "ip": "203.0.113.7",
                "user_agent": "Mozilla/5.0",
            },
        )
        row = db.scalars(select(Subscriber)).one()
        assert row.email == "someone@example.com"
        assert not hasattr(row, "ip")
