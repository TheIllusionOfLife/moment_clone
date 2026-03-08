"""Move pgvector extension from public to extensions schema.

Supabase's security advisor flags extensions installed in the public schema.
The extensions schema already exists and is already in the default search_path
("$user", public, extensions), so all existing column types and unqualified
references (e.g. CAST(:vec AS vector)) continue to resolve without changes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-08
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER EXTENSION vector SET SCHEMA extensions;")


def downgrade() -> None:
    op.execute("ALTER EXTENSION vector SET SCHEMA public;")
