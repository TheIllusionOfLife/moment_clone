"""Tests for pipeline/stages/coaching_script.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.models.chat import Message
from backend.models.dish import Dish
from backend.models.learner_state import LearnerState
from backend.models.session import CookingSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    session_id: int = 1,
    user_id: int = 10,
    dish_id: int = 5,
    session_number: int = 1,
    raw_video_url: str = "sessions/1/raw.mp4",
    video_analysis: dict | None = None,
    structured_input: dict | None = None,
) -> CookingSession:
    s = CookingSession(
        user_id=user_id,
        dish_id=dish_id,
        session_number=session_number,
        status="processing",
        raw_video_url=raw_video_url,
        video_analysis=video_analysis or {"diagnosis": "火加減が強すぎた"},
        structured_input=structured_input,
    )
    s.id = session_id
    return s


def _make_dish(dish_id: int = 5) -> Dish:
    d = Dish(
        slug="chahan",
        name_ja="チャーハン",
        name_en="Fried Rice",
        description_ja="炒飯",
        order=1,
        principles=["水分を飛ばす", "高温で炒める"],
    )
    d.id = dish_id
    return d


_VALID_COACHING_JSON = {
    "mondaiten": "火加減が強すぎて焦げた",
    "skill": "フライパンの温度管理",
    "next_action": "中火でゆっくり炒める",
    "success_sign": "煙が少なく均一に炒まる",
}

_RETRIEVED_CONTEXT = {
    "principles": ["原則1: 水分管理", "原則2: 高温調理"],
    "session_summaries": [{"session_id": 0, "mondaiten": "塩加減"}],
}


def _make_gemini_response(payload: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(payload)
    return mock_resp


def _make_mock_genai_client(response: MagicMock) -> MagicMock:
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = response
    return MagicMock(return_value=mock_client_instance)


# ---------------------------------------------------------------------------
# test_run_coaching_script_success
# ---------------------------------------------------------------------------


def test_run_coaching_script_success(
    engine, user, dish, cooking_session, learner_state, coaching_room, cooking_videos_room
):
    """Happy path: Gemini returns valid JSON, messages are posted, coaching_text returned."""
    gemini_response = _make_gemini_response(_VALID_COACHING_JSON)
    mock_genai_cls = _make_mock_genai_client(gemini_response)

    with (
        patch(
            "pipeline.stages.coaching_script.get_session_with_dish",
            return_value=(cooking_session, dish),
        ),
        patch("pipeline.stages.coaching_script.update_session_fields"),
        patch("pipeline.stages.coaching_script.get_engine", return_value=engine),
        patch("pipeline.stages.coaching_script.genai.Client", mock_genai_cls),
    ):
        from pipeline.stages.coaching_script import run_coaching_script

        result = run_coaching_script(cooking_session.id, _RETRIEVED_CONTEXT)

    assert result == _VALID_COACHING_JSON

    # Coaching message was posted to coaching room
    from sqlmodel import Session as DBSession
    from sqlmodel import select

    with DBSession(engine) as db:
        coaching_msgs = db.exec(
            select(Message).where(Message.chat_room_id == coaching_room.id)
        ).all()
        video_msgs = db.exec(
            select(Message).where(Message.chat_room_id == cooking_videos_room.id)
        ).all()

    assert len(coaching_msgs) == 1
    assert coaching_msgs[0].sender == "ai"
    assert "フィードバック" in coaching_msgs[0].text

    assert len(video_msgs) == 1
    assert video_msgs[0].sender == "system"
    assert video_msgs[0].video_gcs_path == cooking_session.raw_video_url


# ---------------------------------------------------------------------------
# test_run_coaching_script_missing_key_raises
# ---------------------------------------------------------------------------


def test_run_coaching_script_missing_key_raises(engine, user, dish, cooking_session, learner_state):
    """Gemini response missing 'mondaiten' raises ValueError."""
    bad_payload = {
        "skill": "フライパンの温度管理",
        "next_action": "中火でゆっくり炒める",
        "success_sign": "煙が少なく均一に炒まる",
        # "mondaiten" intentionally omitted
    }
    gemini_response = _make_gemini_response(bad_payload)
    mock_genai_cls = _make_mock_genai_client(gemini_response)

    with (
        patch(
            "pipeline.stages.coaching_script.get_session_with_dish",
            return_value=(cooking_session, dish),
        ),
        patch("pipeline.stages.coaching_script.update_session_fields"),
        patch("pipeline.stages.coaching_script.get_engine", return_value=engine),
        patch("pipeline.stages.coaching_script.genai.Client", mock_genai_cls),
    ):
        from pipeline.stages.coaching_script import run_coaching_script

        with pytest.raises(ValueError, match="mondaiten"):
            run_coaching_script(cooking_session.id, _RETRIEVED_CONTEXT)


# ---------------------------------------------------------------------------
# test_run_coaching_script_learner_state_null_guard
# ---------------------------------------------------------------------------


def test_run_coaching_script_learner_state_null_guard(
    engine, user, dish, cooking_session, coaching_room, cooking_videos_room
):
    """LearnerState with all None lists: no AttributeError raised (null guard works)."""
    # Deliberately do NOT create a learner_state fixture — the stage must create it
    gemini_response = _make_gemini_response(_VALID_COACHING_JSON)
    mock_genai_cls = _make_mock_genai_client(gemini_response)

    with (
        patch(
            "pipeline.stages.coaching_script.get_session_with_dish",
            return_value=(cooking_session, dish),
        ),
        patch("pipeline.stages.coaching_script.update_session_fields"),
        patch("pipeline.stages.coaching_script.get_engine", return_value=engine),
        patch("pipeline.stages.coaching_script.genai.Client", mock_genai_cls),
    ):
        from pipeline.stages.coaching_script import run_coaching_script

        # Must not raise AttributeError despite all LearnerState lists being None
        result = run_coaching_script(cooking_session.id, _RETRIEVED_CONTEXT)

    assert result == _VALID_COACHING_JSON

    # LearnerState row was created with session_summary appended
    from sqlmodel import Session as DBSession
    from sqlmodel import select

    with DBSession(engine) as db:
        ls = db.exec(select(LearnerState).where(LearnerState.user_id == user.id)).first()
    assert ls is not None
    assert ls.session_summaries is not None
    assert len(ls.session_summaries) == 1
    assert ls.session_summaries[0]["session_id"] == cooking_session.id


# ---------------------------------------------------------------------------
# test_format_coaching_text
# ---------------------------------------------------------------------------


def test_format_coaching_text():
    """format_coaching_text produces correctly structured Japanese coaching message."""
    from pipeline.stages.coaching_script import format_coaching_text

    text = format_coaching_text(_VALID_COACHING_JSON, session_number=1)

    assert "【第1回フィードバック】" in text
    assert "■ 今回の課題" in text
    assert _VALID_COACHING_JSON["mondaiten"] in text
    assert "■ 磨くべきスキル" in text
    assert _VALID_COACHING_JSON["skill"] in text
    assert "■ 次回への課題" in text
    assert _VALID_COACHING_JSON["next_action"] in text
    assert "■ うまくいったサイン" in text
    assert _VALID_COACHING_JSON["success_sign"] in text


def test_format_coaching_text_session_number_3():
    """Session number is interpolated correctly for session 3."""
    from pipeline.stages.coaching_script import format_coaching_text

    text = format_coaching_text(_VALID_COACHING_JSON, session_number=3)
    assert "【第3回フィードバック】" in text
