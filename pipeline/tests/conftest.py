"""Shared pytest fixtures for the pipeline test suite."""

import os

# Set required env vars before any backend module is imported so that
# module-level singletons (Inngest CommHandler, pydantic-settings) initialise
# without external credentials.
os.environ.setdefault("INNGEST_DEV", "1")
os.environ.setdefault("INNGEST_EVENT_KEY", "test-event-key")
os.environ.setdefault("INNGEST_SIGNING_KEY", "signkey-test-00000000000000000000000000000000")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("CLERK_JWKS_URL", "http://localhost/jwks")
os.environ.setdefault("CLERK_WEBHOOK_SECRET", "whsec_testonly")
os.environ.setdefault("GEMINI_API_KEY", "test-api-key")
os.environ.setdefault("GCS_BUCKET", "test-bucket")

import pytest
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.models.chat import ChatRoom
from backend.models.dish import Dish
from backend.models.learner_state import LearnerState
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
    with DBSession(engine) as session:
        yield session


@pytest.fixture(name="user")
def user_fixture(db):
    u = User(clerk_user_id="user_abc123", email="test@example.com", first_name="Test")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture(name="dish")
def dish_fixture(db):
    d = Dish(
        slug="chahan",
        name_ja="チャーハン",
        name_en="Fried Rice",
        description_ja="炒飯",
        order=1,
        principles=["水分を飛ばす", "高温で炒める"],
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@pytest.fixture(name="cooking_session")
def cooking_session_fixture(db, user, dish):
    s = CookingSession(
        user_id=user.id,
        dish_id=dish.id,
        session_number=1,
        raw_video_url="sessions/1/raw.mp4",
        status="processing",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture(name="learner_state")
def learner_state_fixture(db, user):
    ls = LearnerState(user_id=user.id)
    db.add(ls)
    db.commit()
    db.refresh(ls)
    return ls


@pytest.fixture(name="coaching_room")
def coaching_room_fixture(db, user):
    room = ChatRoom(user_id=user.id, room_type="coaching")
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@pytest.fixture(name="cooking_videos_room")
def cooking_videos_room_fixture(db, user):
    room = ChatRoom(user_id=user.id, room_type="cooking_videos")
    db.add(room)
    db.commit()
    db.refresh(room)
    return room
