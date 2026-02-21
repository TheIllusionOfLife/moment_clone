"""Tests for pipeline/stages/video_production.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

SAMPLE_NARRATION_SCRIPT = {
    "part1": "今日の炒飯の分析をお伝えします。最も重要なポイントは火加減です。",
    "pivot": "動画を使ってそのポイントを見てみましょう",
    "part2": "次回は鍋をしっかり予熱してから炒め始めてください。",
}


def _make_mock_session():
    mock_session = MagicMock()
    mock_session.id = 42
    mock_session.user_id = 7
    mock_session.dish_id = 1
    mock_session.raw_video_url = "sessions/42/raw.mp4"
    mock_session.video_analysis = {"key_moment_seconds": 120}
    return mock_session


def _make_mock_dish():
    mock_dish = MagicMock()
    mock_dish.name_ja = "チャーハン"
    return mock_dish


def _make_subprocess_run_side_effect(part1_duration: float = 60.0, part2_duration: float = 30.0):
    """
    Return a side_effect function for subprocess.run that handles:
    - ffprobe calls: returns JSON with duration
    - ffmpeg calls: returns success (returncode=0)
    """
    call_count = {"n": 0}

    def side_effect(cmd, **kwargs):
        call_count["n"] += 1
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""

        if cmd[0] == "ffprobe":
            # Determine which audio file (part1 or part2) by call order.
            # First ffprobe call → part1 duration, second → part2 duration.
            if call_count["n"] <= 2:  # first ffprobe (call_count includes prior ffmpeg calls)
                duration = part1_duration
            else:
                duration = part2_duration
            result.stdout = json.dumps({"format": {"duration": str(duration)}}).encode()
        else:
            result.stdout = b""

        return result

    return side_effect


# ---------------------------------------------------------------------------
# test_run_ffmpeg_success
# ---------------------------------------------------------------------------


def test_run_ffmpeg_success():
    """_run_ffmpeg does not raise when subprocess exits 0."""
    from pipeline.stages.video_production import _run_ffmpeg

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = b""

    with patch("pipeline.stages.video_production.subprocess.run", return_value=mock_result):
        # Should not raise
        _run_ffmpeg(["-i", "input.mp4", "output.mp4"])


# ---------------------------------------------------------------------------
# test_run_ffmpeg_failure_raises_runtime_error
# ---------------------------------------------------------------------------


def test_run_ffmpeg_failure_raises_runtime_error():
    """_run_ffmpeg raises RuntimeError with stderr content on non-zero exit."""
    from pipeline.stages.video_production import _run_ffmpeg

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b"No such file or directory"

    with patch("pipeline.stages.video_production.subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="No such file or directory"):
            _run_ffmpeg(["-i", "missing.mp4", "output.mp4"])


# ---------------------------------------------------------------------------
# test_run_video_production_success
# ---------------------------------------------------------------------------


def test_run_video_production_success():
    """Happy path: returns GCS path and calls update_session_fields with coaching_video_gcs_path."""
    from pipeline.stages.video_production import run_video_production

    mock_session = _make_mock_session()
    mock_dish = _make_mock_dish()

    # GCS mocks
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs_client = MagicMock()
    mock_gcs_client.bucket.return_value = mock_bucket

    # TTS mock
    mock_tts_response = MagicMock()
    mock_tts_response.audio_content = b"fake-audio-data"
    mock_tts_client = MagicMock()
    mock_tts_client.synthesize_speech.return_value = mock_tts_response

    # subprocess mock (ffprobe + ffmpeg)
    call_counter = {"ffprobe": 0}

    def subprocess_side_effect(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        if cmd[0] == "ffprobe":
            call_counter["ffprobe"] += 1
            if call_counter["ffprobe"] == 1:
                duration = 60.0
            else:
                duration = 30.0
            result.stdout = json.dumps({"format": {"duration": str(duration)}}).encode()
        else:
            result.stdout = b""
        return result

    mock_coaching_room = MagicMock()
    mock_coaching_room.id = 10
    mock_update = MagicMock()
    mock_engine = MagicMock()

    with (
        patch(
            "pipeline.stages.video_production.get_session_with_dish",
            return_value=(mock_session, mock_dish),
        ),
        patch("pipeline.stages.video_production.update_session_fields", mock_update),
        patch("pipeline.stages.video_production.get_engine", return_value=mock_engine),
        patch(
            "pipeline.stages.video_production.get_coaching_room",
            return_value=mock_coaching_room,
        ),
        patch("pipeline.stages.video_production.post_message"),
        patch(
            "pipeline.stages.video_production.storage.Client",
            return_value=mock_gcs_client,
        ),
        patch(
            "pipeline.stages.video_production.texttospeech.TextToSpeechClient",
            return_value=mock_tts_client,
        ),
        patch(
            "pipeline.stages.video_production.subprocess.run",
            side_effect=subprocess_side_effect,
        ),
    ):
        result = run_video_production(42, SAMPLE_NARRATION_SCRIPT)

    expected_gcs_path = "sessions/42/coaching_video.mp4"
    assert result == expected_gcs_path

    mock_update.assert_called_once_with(42, coaching_video_gcs_path=expected_gcs_path)


# ---------------------------------------------------------------------------
# test_video_production_does_not_set_completed_status
# ---------------------------------------------------------------------------


def test_video_production_does_not_set_completed_status():
    """update_session_fields must NOT be called with status='completed'."""
    from pipeline.stages.video_production import run_video_production

    mock_session = _make_mock_session()
    mock_dish = _make_mock_dish()

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs_client = MagicMock()
    mock_gcs_client.bucket.return_value = mock_bucket

    mock_tts_response = MagicMock()
    mock_tts_response.audio_content = b"audio"
    mock_tts_client = MagicMock()
    mock_tts_client.synthesize_speech.return_value = mock_tts_response

    call_counter = {"ffprobe": 0}

    def subprocess_side_effect(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        if cmd[0] == "ffprobe":
            call_counter["ffprobe"] += 1
            duration = 60.0 if call_counter["ffprobe"] == 1 else 30.0
            result.stdout = json.dumps({"format": {"duration": str(duration)}}).encode()
        else:
            result.stdout = b""
        return result

    mock_coaching_room = MagicMock()
    mock_coaching_room.id = 10
    mock_update = MagicMock()
    mock_engine = MagicMock()

    with (
        patch(
            "pipeline.stages.video_production.get_session_with_dish",
            return_value=(mock_session, mock_dish),
        ),
        patch("pipeline.stages.video_production.update_session_fields", mock_update),
        patch("pipeline.stages.video_production.get_engine", return_value=mock_engine),
        patch(
            "pipeline.stages.video_production.get_coaching_room",
            return_value=mock_coaching_room,
        ),
        patch("pipeline.stages.video_production.post_message"),
        patch(
            "pipeline.stages.video_production.storage.Client",
            return_value=mock_gcs_client,
        ),
        patch(
            "pipeline.stages.video_production.texttospeech.TextToSpeechClient",
            return_value=mock_tts_client,
        ),
        patch(
            "pipeline.stages.video_production.subprocess.run",
            side_effect=subprocess_side_effect,
        ),
    ):
        run_video_production(42, SAMPLE_NARRATION_SCRIPT)

    # Verify none of the update_session_fields calls include status="completed"
    for c in mock_update.call_args_list:
        kwargs = c.kwargs if c.kwargs else {}
        args = c.args if c.args else ()
        assert "status" not in kwargs, "update_session_fields must not set status='completed'"
        if len(args) > 1:
            assert "completed" not in args
