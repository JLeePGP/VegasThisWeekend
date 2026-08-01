"""Newsletter signup.

The privacy tests here are not decoration. This is the only table in the project holding
personal data, and the two ways it could quietly become something worse are storing more
than the address and letting the response reveal who is already on the list.
"""

from __future__ import annotations

from sqlalchemy import select

from app.models import Subscriber


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
