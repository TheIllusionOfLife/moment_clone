from datetime import datetime

from sqlmodel import Field, SQLModel


class CookingPrinciple(SQLModel, table=True):
    """Cooking principles for RAG.

    The 'embedding' column is vector(768) managed directly via SQL —
    pgvector type is not natively supported by SQLModel, so it is
    handled in knowledge_base/ingest.py and pipeline/stages/rag.py
    via raw SQL.
    """

    __tablename__ = "cooking_principles"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    principle_text: str
    category: str | None = None
    created_at: datetime | None = Field(default_factory=datetime.utcnow)
