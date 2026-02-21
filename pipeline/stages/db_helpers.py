"""Shared DB utilities for pipeline stages.

All helpers that open their own sessions use get_engine() internally so they
can be called from sync Inngest step handlers. Helpers that accept an explicit
db session are used by stages that need to bundle multiple operations in one
transaction (e.g. coaching_script's LearnerState update).
"""

import json

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DBSession
from sqlmodel import select

from backend.core.database import get_engine
from backend.models.chat import ChatRoom, Message
from backend.models.dish import Dish
from backend.models.learner_state import LearnerState
from backend.models.session import CookingSession


def _parse_json_response(text: str) -> dict:
    """Extract and parse the first JSON object from a Gemini response.

    Uses JSONDecoder.raw_decode to find the exact boundary of the first JSON
    object, handling filler text before/after and nested objects correctly.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    try:
        result, _ = json.JSONDecoder().raw_decode(text, start)
        return result  # type: ignore[no-any-return]
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from response: {text[:200]}") from e


def get_session_with_dish(session_id: int) -> tuple[CookingSession, Dish]:
    """Load a CookingSession and its Dish in a single connection."""
    with DBSession(get_engine()) as db:
        cooking_session = db.get(CookingSession, session_id)
        if cooking_session is None:
            raise ValueError(f"CookingSession {session_id} not found")
        dish = db.get(Dish, cooking_session.dish_id)
        if dish is None:
            raise ValueError(f"Dish {cooking_session.dish_id} not found")
        # Detach from session by expunging so callers can use attributes freely
        db.expunge(cooking_session)
        db.expunge(dish)
        return cooking_session, dish


def update_session_fields(session_id: int, **kwargs: object) -> None:
    """Set arbitrary fields on a CookingSession and commit."""
    with DBSession(get_engine()) as db:
        cooking_session = db.get(CookingSession, session_id)
        if cooking_session is None:
            raise ValueError(f"CookingSession {session_id} not found")
        for key, value in kwargs.items():
            setattr(cooking_session, key, value)
        db.add(cooking_session)
        db.commit()


def get_or_create_learner_state(user_id: int, db: DBSession) -> LearnerState:
    """Return the LearnerState for user_id, creating it if it doesn't exist.

    Uses try/except IntegrityError to handle concurrent inserts safely.
    """
    ls = db.exec(select(LearnerState).where(LearnerState.user_id == user_id)).first()
    if ls is None:
        try:
            ls = LearnerState(user_id=user_id)
            db.add(ls)
            db.commit()
            db.refresh(ls)
        except IntegrityError:
            db.rollback()
            ls = db.exec(select(LearnerState).where(LearnerState.user_id == user_id)).first()
            if ls is None:
                raise
    return ls


def get_coaching_room(user_id: int, db: DBSession) -> ChatRoom:
    room = db.exec(
        select(ChatRoom).where(
            ChatRoom.user_id == user_id,
            ChatRoom.room_type == "coaching",
        )
    ).first()
    if room is None:
        raise ValueError(f"Coaching room not found for user {user_id}")
    return room


def get_cooking_videos_room(user_id: int, db: DBSession) -> ChatRoom:
    room = db.exec(
        select(ChatRoom).where(
            ChatRoom.user_id == user_id,
            ChatRoom.room_type == "cooking_videos",
        )
    ).first()
    if room is None:
        raise ValueError(f"Cooking videos room not found for user {user_id}")
    return room


def post_message(
    chat_room_id: int,
    sender: str,
    session_id: int | None,
    *,
    text: str = "",
    video_gcs_path: str = "",
    msg_metadata: dict | None = None,
    db: DBSession,
) -> Message:
    """Persist a Message row and return the refreshed instance."""
    message = Message(
        chat_room_id=chat_room_id,
        sender=sender,
        session_id=session_id,
        text=text,
        video_gcs_path=video_gcs_path,
        msg_metadata=msg_metadata,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
