"""Embed cooking principles from knowledge_base/*.md and insert into Supabase pgvector.

Usage:
    uv run python -m backend.scripts.seed_knowledge_base
"""

import pathlib
import sys

from sqlmodel import Session

from backend.core.database import get_engine
from knowledge_base.ingest import embed_and_insert

KB_DIR = pathlib.Path(__file__).parent.parent.parent / "knowledge_base"


def seed() -> None:
    md_files = sorted(KB_DIR.glob("*.md"))
    if not md_files:
        print(f"No Markdown files found in {KB_DIR}. Add principle files first.")
        sys.exit(1)

    with Session(get_engine()) as db:
        for md_file in md_files:
            print(f"Ingesting: {md_file.name}")
            embed_and_insert(md_file, db)

    print("Done.")


if __name__ == "__main__":
    seed()
