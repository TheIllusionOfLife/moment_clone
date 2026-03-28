"""Tests for pipeline/stages/db_helpers.py."""

from unittest.mock import patch

import pytest

from pipeline.stages.db_helpers import (
    get_coaching_room,
    get_cooking_videos_room,
    get_or_create_learner_state,
    get_session_with_dish,
    post_message,
    update_session_fields,
)

# ---------------------------------------------------------------------------
# get_session_with_dish
# ---------------------------------------------------------------------------


def test_get_session_with_dish_success(engine, cooking_session, dish):
    with patch("pipeline.stages.db_helpers.get_engine", return_value=engine):
        session, dish_result = get_session_with_dish(cooking_session.id)
    assert session.id == cooking_session.id
    assert dish_result.id == dish.id


def test_get_session_with_dish_not_found(engine):
    with patch("pipeline.stages.db_helpers.get_engine", return_value=engine):
        with pytest.raises(ValueError, match="not found"):
            get_session_with_dish(9999)


# ---------------------------------------------------------------------------
# update_session_fields
# ---------------------------------------------------------------------------


def test_update_session_fields(engine, cooking_session):
    from sqlmodel import Session as DBSession

    from backend.models.session import CookingSession

    with patch("pipeline.stages.db_helpers.get_engine", return_value=engine):
        update_session_fields(cooking_session.id, status="text_ready", voice_transcript="hello")

    with DBSession(engine) as db:
        s = db.get(CookingSession, cooking_session.id)
        assert s.status == "text_ready"
        assert s.voice_transcript == "hello"


def test_update_session_fields_not_found(engine):
    with patch("pipeline.stages.db_helpers.get_engine", return_value=engine):
        with pytest.raises(ValueError, match="not found"):
            update_session_fields(9999, status="text_ready")


# ---------------------------------------------------------------------------
# get_or_create_learner_state
# ---------------------------------------------------------------------------


def test_get_or_create_learner_state_creates(db, user):
    ls = get_or_create_learner_state(user.id, db)
    assert ls.user_id == user.id
    assert ls.id is not None


def test_get_or_create_learner_state_returns_existing(db, user, learner_state):
    ls = get_or_create_learner_state(user.id, db)
    assert ls.id == learner_state.id


# ---------------------------------------------------------------------------
# get_coaching_room / get_cooking_videos_room
# ---------------------------------------------------------------------------


def test_get_coaching_room_success(db, user, coaching_room):
    room = get_coaching_room(user.id, db)
    assert room.id == coaching_room.id
    assert room.room_type == "coaching"


def test_get_coaching_room_not_found(db, user):
    with pytest.raises(ValueError, match="not found"):
        get_coaching_room(user.id, db)


def test_get_cooking_videos_room_success(db, user, cooking_videos_room):
    room = get_cooking_videos_room(user.id, db)
    assert room.id == cooking_videos_room.id
    assert room.room_type == "cooking_videos"


def test_get_cooking_videos_room_not_found(db, user):
    with pytest.raises(ValueError, match="not found"):
        get_cooking_videos_room(user.id, db)


# ---------------------------------------------------------------------------
# post_message
# ---------------------------------------------------------------------------


def test_post_text_message(db, coaching_room, cooking_session):
    msg = post_message(
        coaching_room.id,
        sender="ai",
        session_id=cooking_session.id,
        text="Great job!",
        db=db,
    )
    assert msg.id is not None
    assert msg.sender == "ai"
    assert msg.text == "Great job!"
    assert msg.video_gcs_path == ""
    assert msg.session_id == cooking_session.id


def test_post_video_message(db, coaching_room, cooking_session):
    msg = post_message(
        coaching_room.id,
        sender="ai",
        session_id=cooking_session.id,
        video_gcs_path="sessions/1/coaching_video.mp4",
        db=db,
    )
    assert msg.video_gcs_path == "sessions/1/coaching_video.mp4"
    assert msg.text == ""
