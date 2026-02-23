"""Add pending_gcs_path column to session table.

Stores the GCS object path issued by /upload-url/ so confirm-upload can
validate the client is not supplying an arbitrary path.

Revision ID: 0003
Revises: a008668ec8e0
Create Date: 2026-02-23
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "a008668ec8e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session",
        sa.Column("pending_gcs_path", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session", "pending_gcs_path")
