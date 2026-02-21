"""Baseline revision — schema already exists in Supabase.

This is a no-op migration. The 8 tables (user, dish, userdishprogress,
session, learnerstate, chatroom, message, cooking_principles) and the
pgvector extension were created directly in Supabase before this project
was scaffolded.

Run `alembic stamp 0001` to mark the DB as being at this revision without
executing any DDL. Future schema changes should use:

    uv run alembic revision --autogenerate -m "description"
    uv run alembic upgrade head

Revision ID: 0001
Revises:
Create Date: 2026-02-21
"""

from alembic import op  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # no-op: schema already exists


def downgrade() -> None:
    pass
