"""Tests for pipeline/stages/rag.py."""

from unittest.mock import MagicMock, patch

from backend.models.dish import Dish
from backend.models.learner_state import LearnerState
from backend.models.session import CookingSession


def _make_session(session_id: int = 1, user_id: int = 10, dish_id: int = 5) -> CookingSession:
    s = CookingSession(
        user_id=user_id,
        dish_id=dish_id,
        session_number=1,
        status="processing",
        video_analysis={"diagnosis": "火加減が強すぎた"},
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


def _make_learner_state(user_id: int = 10, session_summaries: list | None = None) -> LearnerState:
    ls = LearnerState(user_id=user_id, session_summaries=session_summaries)
    ls.id = 1
    return ls


# ---------------------------------------------------------------------------
# test_run_rag_returns_principles_and_summaries
# ---------------------------------------------------------------------------


def test_run_rag_returns_principles_and_summaries():
    """RAG returns 3 principles and session summaries from LearnerState."""
    fake_session = _make_session()
    fake_dish = _make_dish()
    fake_ls = _make_learner_state(session_summaries=[{"session_id": 1, "mondaiten": "火加減"}])

    # Fake embedding values
    fake_embedding = [0.1] * 768

    # Fake rows returned by pgvector query
    fake_rows = [
        ("原則1: 水分管理",),
        ("原則2: 高温調理",),
        ("原則3: 塩分バランス",),
    ]

    # Mock genai.Client
    mock_embed_response = MagicMock()
    mock_embed_response.embeddings = [MagicMock(values=fake_embedding)]
    mock_client_instance = MagicMock()
    mock_client_instance.models.embed_content.return_value = mock_embed_response
    mock_genai_client_cls = MagicMock(return_value=mock_client_instance)

    # Mock db.execute for pgvector query
    mock_db_execute_result = MagicMock()
    mock_db_execute_result.fetchall.return_value = fake_rows
    mock_db_session = MagicMock()
    mock_db_session.__enter__ = MagicMock(return_value=mock_db_session)
    mock_db_session.__exit__ = MagicMock(return_value=False)
    mock_db_session.execute.return_value = mock_db_execute_result
    mock_db_session_cls = MagicMock(return_value=mock_db_session)

    mock_engine = MagicMock()

    with (
        patch("pipeline.stages.rag.get_session_with_dish", return_value=(fake_session, fake_dish)),
        patch("pipeline.stages.rag.get_or_create_learner_state", return_value=fake_ls),
        patch("pipeline.stages.rag.get_engine", return_value=mock_engine),
        patch("pipeline.stages.rag.genai.Client", mock_genai_client_cls),
        patch("pipeline.stages.rag.DBSession", mock_db_session_cls),
    ):
        from pipeline.stages.rag import run_rag

        result = run_rag(1)

    assert "principles" in result
    assert "session_summaries" in result
    assert len(result["principles"]) == 3
    assert result["principles"][0] == "原則1: 水分管理"
    assert result["principles"][1] == "原則2: 高温調理"
    assert result["principles"][2] == "原則3: 塩分バランス"
    assert result["session_summaries"] == [{"session_id": 1, "mondaiten": "火加減"}]


# ---------------------------------------------------------------------------
# test_run_rag_empty_session_summaries
# ---------------------------------------------------------------------------


def test_run_rag_empty_session_summaries():
    """When LearnerState.session_summaries is None, return empty list."""
    fake_session = _make_session()
    fake_dish = _make_dish()
    # session_summaries is None
    fake_ls = _make_learner_state(session_summaries=None)

    fake_embedding = [0.0] * 768
    fake_rows = [("原則A",), ("原則B",), ("原則C",)]

    mock_embed_response = MagicMock()
    mock_embed_response.embeddings = [MagicMock(values=fake_embedding)]
    mock_client_instance = MagicMock()
    mock_client_instance.models.embed_content.return_value = mock_embed_response
    mock_genai_client_cls = MagicMock(return_value=mock_client_instance)

    mock_db_execute_result = MagicMock()
    mock_db_execute_result.fetchall.return_value = fake_rows
    mock_db_session = MagicMock()
    mock_db_session.__enter__ = MagicMock(return_value=mock_db_session)
    mock_db_session.__exit__ = MagicMock(return_value=False)
    mock_db_session.execute.return_value = mock_db_execute_result
    mock_db_session_cls = MagicMock(return_value=mock_db_session)

    mock_engine = MagicMock()

    with (
        patch("pipeline.stages.rag.get_session_with_dish", return_value=(fake_session, fake_dish)),
        patch("pipeline.stages.rag.get_or_create_learner_state", return_value=fake_ls),
        patch("pipeline.stages.rag.get_engine", return_value=mock_engine),
        patch("pipeline.stages.rag.genai.Client", mock_genai_client_cls),
        patch("pipeline.stages.rag.DBSession", mock_db_session_cls),
    ):
        from pipeline.stages.rag import run_rag

        result = run_rag(1)

    assert result["session_summaries"] == []


# ---------------------------------------------------------------------------
# test_run_rag_limits_summaries_to_last_5
# ---------------------------------------------------------------------------


def test_run_rag_limits_summaries_to_last_5():
    """When LearnerState has 8 session summaries, only the last 5 are returned."""
    fake_session = _make_session()
    fake_dish = _make_dish()
    summaries_8 = [{"session_id": i, "mondaiten": f"課題{i}"} for i in range(1, 9)]
    fake_ls = _make_learner_state(session_summaries=summaries_8)

    fake_embedding = [0.0] * 768
    fake_rows = [("原則X",), ("原則Y",), ("原則Z",)]

    mock_embed_response = MagicMock()
    mock_embed_response.embeddings = [MagicMock(values=fake_embedding)]
    mock_client_instance = MagicMock()
    mock_client_instance.models.embed_content.return_value = mock_embed_response
    mock_genai_client_cls = MagicMock(return_value=mock_client_instance)

    mock_db_execute_result = MagicMock()
    mock_db_execute_result.fetchall.return_value = fake_rows
    mock_db_session = MagicMock()
    mock_db_session.__enter__ = MagicMock(return_value=mock_db_session)
    mock_db_session.__exit__ = MagicMock(return_value=False)
    mock_db_session.execute.return_value = mock_db_execute_result
    mock_db_session_cls = MagicMock(return_value=mock_db_session)

    mock_engine = MagicMock()

    with (
        patch("pipeline.stages.rag.get_session_with_dish", return_value=(fake_session, fake_dish)),
        patch("pipeline.stages.rag.get_or_create_learner_state", return_value=fake_ls),
        patch("pipeline.stages.rag.get_engine", return_value=mock_engine),
        patch("pipeline.stages.rag.genai.Client", mock_genai_client_cls),
        patch("pipeline.stages.rag.DBSession", mock_db_session_cls),
    ):
        from pipeline.stages.rag import run_rag

        result = run_rag(1)

    assert len(result["session_summaries"]) == 5
    # Last 5 of 8 = indices 3..7 → session_ids 4..8
    assert result["session_summaries"][0]["session_id"] == 4
    assert result["session_summaries"][-1]["session_id"] == 8
