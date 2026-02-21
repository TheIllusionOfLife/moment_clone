"""Shared pytest fixtures for the backend test suite."""

import os

# Set required env vars before any backend module is imported so that
# module-level singletons (Inngest CommHandler, pydantic-settings) initialise
# without external credentials.
os.environ.setdefault("INNGEST_DEV", "1")  # disables signing key requirement
os.environ.setdefault("INNGEST_EVENT_KEY", "test-event-key")
os.environ.setdefault("INNGEST_SIGNING_KEY", "signkey-test-00000000000000000000000000000000")
os.environ.setdefault("DATABASE_URL", "sqlite://")  # overridden by fixture
os.environ.setdefault("CLERK_JWKS_URL", "http://localhost/jwks")
os.environ.setdefault("CLERK_WEBHOOK_SECRET", "whsec_testonly")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import Session, SQLModel, create_engine

from backend.models.dish import Dish
from backend.models.session import CookingSession
from backend.models.user import User


@pytest.fixture(name="db_path")
def db_path_fixture(tmp_path):
    """Temporary file-based SQLite database path shared between sync and async engines."""
    return str(tmp_path / "test.db")


@pytest.fixture(name="engine")
def engine_fixture(db_path):
    """Sync SQLite engine with all tables created."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest_asyncio.fixture(name="async_engine")
async def async_engine_fixture(db_path, engine):
    """Async SQLite engine sharing the same file-based database as the sync engine."""
    # engine fixture is a dependency to ensure tables are created first
    async_eng = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    yield async_eng
    await async_eng.dispose()


@pytest.fixture(name="db")
def db_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest_asyncio.fixture(name="async_db")
async def async_db_fixture(async_engine):
    async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session


@pytest.fixture(name="user")
def user_fixture(db):
    u = User(clerk_user_id="user_abc123", email="test@example.com", first_name="Test")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture(name="other_user")
def other_user_fixture(db):
    u = User(clerk_user_id="user_xyz999", email="other@example.com", first_name="Other")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture(name="dish")
def dish_fixture(db):
    d = Dish(
        slug="chahan", name_ja="チャーハン", name_en="Fried Rice", description_ja="炒飯", order=1
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@pytest.fixture(name="cooking_session")
def cooking_session_fixture(db, user, dish):
    s = CookingSession(user_id=user.id, dish_id=dish.id, session_number=1)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture(name="app")
def app_fixture(engine, async_engine):
    """FastAPI TestClient with DB overridden to use test SQLite."""
    from backend.core.database import get_async_session, get_session
    from backend.main import app

    def override_get_session():
        with Session(engine) as session:
            yield session

    async def override_get_async_session():
        async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with async_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_async_session] = override_get_async_session
    yield app
    app.dependency_overrides.clear()
