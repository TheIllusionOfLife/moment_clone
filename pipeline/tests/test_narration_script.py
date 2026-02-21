"""Tests for pipeline/stages/narration_script.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

PIVOT_LINE = "動画を使ってそのポイントを見てみましょう"

SAMPLE_COACHING_TEXT = {
    "mondaiten": "火加減が弱すぎてメイラード反応が起きていない",
    "skill": "強火で短時間炒める技術",
    "next_action": "次回は中華鍋を煙が出るまで予熱してから炒め始める",
    "success_sign": "ご飯がパラパラになり、少し焦げ目がつく",
}

SAMPLE_NARRATION_RESPONSE = {
    "part1": "今日は炒飯の調理を分析しました。最も重要なポイントは火加減です。",
    "pivot": "動画でそのポイントを確認しましょう",  # intentionally different from PIVOT_LINE
    "part2": "次回の練習では、鍋を十分に予熱してから炒め始めることを意識してください。",
}


def _make_mock_session_and_dish():
    """Return (mock_session, mock_dish) with common defaults."""
    mock_session = MagicMock()
    mock_session.id = 42
    mock_session.user_id = 1
    mock_session.dish_id = 1

    mock_dish = MagicMock()
    mock_dish.name_ja = "チャーハン"
    mock_dish.name_en = "Fried Rice"

    return mock_session, mock_dish


def _make_mock_gemini_response(data: dict) -> MagicMock:
    """Return a mock Gemini response whose .text is JSON-encoded data."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(data)
    return mock_response


# ---------------------------------------------------------------------------
# test_run_narration_script_success
# ---------------------------------------------------------------------------


def test_run_narration_script_success():
    """Happy path: returns dict with part1, part2, and the fixed pivot."""
    from pipeline.stages.narration_script import run_narration_script

    mock_session, mock_dish = _make_mock_session_and_dish()
    mock_response = _make_mock_gemini_response(SAMPLE_NARRATION_RESPONSE)

    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content.return_value = mock_response

    with (
        patch(
            "pipeline.stages.narration_script.get_session_with_dish",
            return_value=(mock_session, mock_dish),
        ),
        patch(
            "pipeline.stages.narration_script.update_session_fields",
        ),
        patch(
            "pipeline.stages.narration_script.genai.Client",
            return_value=mock_gemini_client,
        ),
    ):
        result = run_narration_script(42, SAMPLE_COACHING_TEXT)

    assert "part1" in result
    assert "part2" in result
    assert "pivot" in result
    assert result["pivot"] == PIVOT_LINE
    assert result["part1"] == SAMPLE_NARRATION_RESPONSE["part1"]
    assert result["part2"] == SAMPLE_NARRATION_RESPONSE["part2"]


# ---------------------------------------------------------------------------
# test_pivot_always_overridden
# ---------------------------------------------------------------------------


def test_pivot_always_overridden():
    """Gemini returns a different pivot; verify it is replaced with PIVOT_LINE."""
    from pipeline.stages.narration_script import run_narration_script

    mock_session, mock_dish = _make_mock_session_and_dish()

    # Gemini returns a completely different pivot line
    different_pivot_response = {
        "part1": "Part 1 content here.",
        "pivot": "これは別のピボットラインです",  # not the fixed string
        "part2": "Part 2 content here.",
    }
    mock_response = _make_mock_gemini_response(different_pivot_response)

    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content.return_value = mock_response

    with (
        patch(
            "pipeline.stages.narration_script.get_session_with_dish",
            return_value=(mock_session, mock_dish),
        ),
        patch("pipeline.stages.narration_script.update_session_fields"),
        patch(
            "pipeline.stages.narration_script.genai.Client",
            return_value=mock_gemini_client,
        ),
    ):
        result = run_narration_script(42, SAMPLE_COACHING_TEXT)

    assert result["pivot"] == PIVOT_LINE
    assert result["pivot"] != "これは別のピボットラインです"


# ---------------------------------------------------------------------------
# test_missing_part1_raises
# ---------------------------------------------------------------------------


def test_missing_part1_raises():
    """Gemini response missing 'part1' key raises ValueError."""
    from pipeline.stages.narration_script import run_narration_script

    mock_session, mock_dish = _make_mock_session_and_dish()

    # Missing part1
    incomplete_response = {
        "pivot": "some pivot",
        "part2": "Part 2 content.",
    }
    mock_response = _make_mock_gemini_response(incomplete_response)

    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content.return_value = mock_response

    with (
        patch(
            "pipeline.stages.narration_script.get_session_with_dish",
            return_value=(mock_session, mock_dish),
        ),
        patch("pipeline.stages.narration_script.update_session_fields"),
        patch(
            "pipeline.stages.narration_script.genai.Client",
            return_value=mock_gemini_client,
        ),
    ):
        with pytest.raises(ValueError):
            run_narration_script(42, SAMPLE_COACHING_TEXT)


# ---------------------------------------------------------------------------
# test_run_narration_script_persists
# ---------------------------------------------------------------------------


def test_run_narration_script_persists():
    """update_session_fields is called with narration_script containing the result."""
    from pipeline.stages.narration_script import run_narration_script

    mock_session, mock_dish = _make_mock_session_and_dish()
    mock_response = _make_mock_gemini_response(SAMPLE_NARRATION_RESPONSE)

    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content.return_value = mock_response

    mock_update = MagicMock()

    with (
        patch(
            "pipeline.stages.narration_script.get_session_with_dish",
            return_value=(mock_session, mock_dish),
        ),
        patch(
            "pipeline.stages.narration_script.update_session_fields",
            mock_update,
        ),
        patch(
            "pipeline.stages.narration_script.genai.Client",
            return_value=mock_gemini_client,
        ),
    ):
        result = run_narration_script(42, SAMPLE_COACHING_TEXT)

    mock_update.assert_called_once()
    call_kwargs = mock_update.call_args.kwargs
    assert "narration_script" in call_kwargs
    persisted = call_kwargs["narration_script"]
    assert persisted["pivot"] == PIVOT_LINE
    assert persisted == result
