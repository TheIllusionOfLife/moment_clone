from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
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


_async_engine: AsyncEngine | None = None


def get_async_engine() -> AsyncEngine:
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(settings.ASYNC_DATABASE_URL, pool_pre_ping=True)
    return _async_engine


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async_session_factory = async_sessionmaker(get_async_engine(), expire_on_commit=False)
    async with async_session_factory() as session:
        yield session
