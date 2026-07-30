"""add stat_counters

Purely additive: one new table, nothing on existing tables touched.

The two unique indexes are partial and cannot be collapsed into one. A single unique
index over (day, metric, event_id) would not prevent duplicate site-wide rows, because
in both Postgres and SQLite two NULLs are not considered equal — every site-wide insert
would happily create another row and the upsert would never find a conflict to resolve.

Revision ID: c93f18de4a77
Revises: b2c7d41ae903
Create Date: 2026-07-30 14:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c93f18de4a77"
down_revision: Union[str, Sequence[str], None] = "b2c7d41ae903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stat_counters",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=32), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stat_counters_day_metric", "stat_counters", ["day", "metric"])
    op.create_index("ix_stat_counters_event", "stat_counters", ["event_id"])
    op.create_index(
        "uq_stat_counters_event",
        "stat_counters",
        ["day", "metric", "event_id"],
        unique=True,
        sqlite_where=sa.text("event_id IS NOT NULL"),
        postgresql_where=sa.text("event_id IS NOT NULL"),
    )
    op.create_index(
        "uq_stat_counters_sitewide",
        "stat_counters",
        ["day", "metric"],
        unique=True,
        sqlite_where=sa.text("event_id IS NULL"),
        postgresql_where=sa.text("event_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_stat_counters_sitewide", table_name="stat_counters")
    op.drop_index("uq_stat_counters_event", table_name="stat_counters")
    op.drop_index("ix_stat_counters_event", table_name="stat_counters")
    op.drop_index("ix_stat_counters_day_metric", table_name="stat_counters")
    op.drop_table("stat_counters")
