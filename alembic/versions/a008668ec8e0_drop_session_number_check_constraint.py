"""Add custom_dish_name column; drop session_number_1_to_3 CHECK constraint.

Free-choice dish (slug='free') sessions store a user-supplied dish name in
custom_dish_name and are not capped at 3 sessions, so the DB-level CHECK
constraint is removed.  Application logic enforces the 3-session cap for
regular dishes.

This migration was never applied to production before merging PR #11 (the
column was added directly in Supabase), so both operations use IF NOT EXISTS /
IF EXISTS guards to be idempotent on any environment.

Revision ID: a008668ec8e0
Revises: 0002
Create Date: 2026-02-22
"""

from alembic import op

revision: str = "a008668ec8e0"
down_revision: str = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the free-dish name column (idempotent — already exists in prod).
    op.execute("ALTER TABLE session ADD COLUMN IF NOT EXISTS custom_dish_name VARCHAR NULL;")
    # Drop the now-obsolete session_number CHECK constraint (idempotent).
    op.execute("ALTER TABLE session DROP CONSTRAINT IF EXISTS session_number_1_to_3;")


def downgrade() -> None:
    op.execute("ALTER TABLE session DROP COLUMN IF EXISTS custom_dish_name;")
    # WARNING: unsafe if free-dish sessions with session_number > 3 already exist.
    # Those rows must be deleted first or this constraint will fail.
    op.execute(
        "ALTER TABLE session ADD CONSTRAINT session_number_1_to_3 "
        "CHECK (session_number IN (1, 2, 3));"
    )
