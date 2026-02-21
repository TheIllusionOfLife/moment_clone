from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from backend.core.settings import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return _engine


# Keep a module-level alias for Alembic and pipeline code that imports `engine` directly.
# The actual Engine is created on first access.
class _LazyEngine:
    def __getattr__(self, name: str):  # type: ignore[override]
        return getattr(get_engine(), name)


engine = _LazyEngine()  # type: ignore[assignment]


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
