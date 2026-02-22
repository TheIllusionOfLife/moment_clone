"""Add onboarding_done column to user table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("onboarding_done", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("user", "onboarding_done")
