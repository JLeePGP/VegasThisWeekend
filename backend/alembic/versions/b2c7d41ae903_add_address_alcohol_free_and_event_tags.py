"""add address, alcohol_free and event_tags

Deliberately additive. Nothing is dropped, renamed or rewritten, so it is safe to run
against a database whose backup situation is unconfirmed, and it is reversible without
data loss.

In particular `neighborhood` stays exactly as it is. `address` is the field we actually
want long term, but replacing the column in the same step would mean rewriting every
existing row from a value we do not have yet. Populate addresses first, confirm the
derived neighbourhoods look right, then drop the old column in a later migration.

Revision ID: b2c7d41ae903
Revises: f79d50b8e5d9
Create Date: 2026-07-30 12:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c7d41ae903"
down_revision: Union[str, Sequence[str], None] = "f79d50b8e5d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("address", sa.String(length=240), nullable=True))

    # server_default is required, not cosmetic: the column is NOT NULL and the table
    # already has rows, so without it the ALTER fails on Postgres.
    #
    # It is also deliberately *kept*. An earlier version of this migration dropped it
    # again with alter_column, on the reasoning that the application default should be
    # the only thing writing new rows. That is not portable: SQLite has no ALTER COLUMN,
    # so the statement raised, the migration aborted halfway with the first two columns
    # added and event_tags never created, and the revision was left unstamped — a
    # partially-applied migration that reported itself as not applied. It happened to
    # work on Postgres, which is exactly what makes it a trap: it would have passed
    # review, passed staging on Postgres, and broken every local SQLite database.
    #
    # Leaving the default in place costs nothing — the app always sends a value — and
    # keeps this migration a single portable step.
    op.add_column(
        "events",
        sa.Column("alcohol_free", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_events_alcohol_free", "events", ["alcohol_free"])

    op.create_table(
        "event_tags",
        sa.Column("event_id", sa.String(length=32), nullable=False),
        sa.Column("tag", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "tag"),
    )
    op.create_index("ix_event_tags_tag", "event_tags", ["tag"])

    # No backfill, deliberately. event_tags holds only the *additional* categories, and
    # the category filter tests the events.vibe column as well as this table — so an
    # event with no tag rows still appears under its own category. An earlier draft
    # stored the primary vibe here too and filtered on this table alone; that made the
    # backfill load-bearing, and any event created without tag rows silently vanished
    # from its own category. Additive-only removes the failure mode instead of relying
    # on remembering to maintain it.


def downgrade() -> None:
    op.drop_index("ix_event_tags_tag", table_name="event_tags")
    op.drop_table("event_tags")
    op.drop_index("ix_events_alcohol_free", table_name="events")
    op.drop_column("events", "alcohol_free")
    op.drop_column("events", "address")
