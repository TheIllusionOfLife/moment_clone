"""Ingest Markdown knowledge base files into Supabase pgvector.

Each Markdown file maps to a set of cooking principles.
H2 headings (##) become categories; bullet list items become principle texts.

Usage (via seed script):
    uv run python -m backend.scripts.seed_knowledge_base
"""

import pathlib

import google.generativeai as genai
from sqlalchemy import text
from sqlmodel import Session

from backend.core.settings import settings

genai.configure(api_key=settings.GEMINI_API_KEY)


def _parse_principles(md_path: pathlib.Path) -> list[tuple[str, str]]:
    """Return list of (category, principle_text) from a Markdown file."""
    content = md_path.read_text(encoding="utf-8")
    current_category = md_path.stem  # fallback: filename without extension
    principles: list[tuple[str, str]] = []

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("## "):
            current_category = line[3:].strip()
        elif line.startswith(("- ", "* ")):
            principle_text = line[2:].strip()
            if principle_text:
                principles.append((current_category, principle_text))

    return principles


def _embed(text_content: str) -> list[float]:
    result = genai.embed_content(
        model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
        content=text_content,
    )
    return result["embedding"]  # type: ignore[return-value]


def embed_and_insert(md_path: pathlib.Path, db: Session) -> None:
    principles = _parse_principles(md_path)
    inserted = 0

    for category, principle_text in principles:
        embedding = _embed(principle_text)
        # pgvector expects the literal array syntax: '[0.1,0.2,...]'
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        db.execute(
            text(
                """
                INSERT INTO cooking_principles (principle_text, category, embedding)
                VALUES (:text, :category, :embedding::vector)
                ON CONFLICT DO NOTHING
                """
            ),
            {"text": principle_text, "category": category, "embedding": embedding_str},
        )
        inserted += 1

    db.commit()
    print(f"  {md_path.name}: {inserted} principles ingested")
