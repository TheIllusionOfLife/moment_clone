"""Enable Row Level Security on all public schema tables.

PostgREST (Supabase auto-generated API) exposes every table without RLS as
publicly readable/writable via the anon key. Our backend connects via
service_role (direct PostgreSQL) which bypasses RLS, so enabling RLS with
no policies has zero impact on FastAPI while fully blocking PostgREST access.

Revision ID: 0005
Revises: 0003
Create Date: 2026-03-08
"""

from alembic import op

revision = "0005"
down_revision = "0003"
branch_labels = None
depends_on = None

TABLES = [
    "alembic_version",
    '"user"',
    "dish",
    "session",
    "learnerstate",
    "chatroom",
    "message",
    "userdishprogress",
    "cooking_principles",
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
