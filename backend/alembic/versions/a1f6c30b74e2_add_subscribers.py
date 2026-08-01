"""add subscribers

One new table, nothing existing touched.

The unique index on `email` is the whole mechanism behind signing up twice being
harmless: the endpoint does not check-then-insert, it inserts and treats a uniqueness
violation as success. A check-then-insert would both race and answer the question "is
this address already on the list", which is not a question a public endpoint should
answer about someone else's email.

Revision ID: a1f6c30b74e2
Revises: d4a81f3c62b0
Create Date: 2026-08-01 10:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f6c30b74e2"
down_revision: Union[str, Sequence[str], None] = "d4a81f3c62b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscribers",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscribers_email", "subscribers", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_subscribers_email", table_name="subscribers")
    op.drop_table("subscribers")
