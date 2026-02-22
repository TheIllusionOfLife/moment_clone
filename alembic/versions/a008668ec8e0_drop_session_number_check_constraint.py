"""Drop session_number_1_to_3 CHECK constraint to allow free-dish sessions beyond 3.

The application logic already enforces a 3-session cap for regular dishes.
The free-choice dish (slug='free') is intentionally unlimited, so the DB-level
CHECK constraint is removed.  Business rule enforcement stays in the router.

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
    op.execute("ALTER TABLE session DROP CONSTRAINT IF EXISTS session_number_1_to_3;")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE session ADD CONSTRAINT session_number_1_to_3 "
        "CHECK (session_number IN (1, 2, 3));"
    )
