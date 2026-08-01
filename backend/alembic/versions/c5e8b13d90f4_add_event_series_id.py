"""add events.series_id

One nullable column and an index. No existing row is read or written.

The backfill that is deliberately *not* here: production has a three-night run sharing a
name and a venue, and grouping it automatically would mean deciding that "same name, same
venue" implies "same series". That is also what two separate runs of an annual event look
like, and a migration is the worst place to make that judgement — it runs unattended, on
data nobody is looking at, with no way to say no. Linking is an explicit action in the
admin panel instead, where John can see exactly which nights are about to be grouped.

Revision ID: c5e8b13d90f4
Revises: a1f6c30b74e2
Create Date: 2026-08-01 19:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e8b13d90f4"
down_revision: Union[str, Sequence[str], None] = "a1f6c30b74e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("series_id", sa.String(length=32), nullable=True))
    op.create_index("ix_events_series_id", "events", ["series_id"])


def downgrade() -> None:
    op.drop_index("ix_events_series_id", table_name="events")
    op.drop_column("events", "series_id")
