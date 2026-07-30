"""add extraction_drafts

One new table, nothing existing touched.

Deliberately no foreign key to events on `event_id`. A draft outlives the event it
produced — the point of keeping approved rows is knowing which URLs have already been
dealt with — and a cascade would delete that history the moment an event was removed.

Revision ID: d4a81f3c62b0
Revises: c93f18de4a77
Create Date: 2026-07-30 16:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a81f3c62b0"
down_revision: Union[str, Sequence[str], None] = "c93f18de4a77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extraction_drafts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=True),
        sa.Column("draft", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("event_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extraction_drafts_status", "extraction_drafts", ["status"])
    op.create_index("ix_extraction_drafts_batch_id", "extraction_drafts", ["batch_id"])
    op.create_index("ix_extraction_drafts_created", "extraction_drafts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_extraction_drafts_created", table_name="extraction_drafts")
    op.drop_index("ix_extraction_drafts_batch_id", table_name="extraction_drafts")
    op.drop_index("ix_extraction_drafts_status", table_name="extraction_drafts")
    op.drop_table("extraction_drafts")
