"""Add webhook_event table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-23
"""

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_event",
        sa.Column("id", sqlmodel.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("webhook_event")
