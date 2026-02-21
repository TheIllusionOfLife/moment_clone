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
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.models.dish import Dish
from backend.models.session import CookingSession
from backend.models.user import User


@pytest.fixture(name="engine")
def engine_fixture():
    """In-memory SQLite engine with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="db")
def db_fixture(engine):
    with Session(engine) as session:
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
def app_fixture(engine):
    """FastAPI TestClient with DB overridden to use in-memory SQLite."""
    from backend.core.database import get_session
    from backend.main import app

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield app
    app.dependency_overrides.clear()
