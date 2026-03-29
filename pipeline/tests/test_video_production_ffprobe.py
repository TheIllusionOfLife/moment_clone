"""Tests for FFprobe output parsing in video_production._get_audio_duration."""

import json
from unittest.mock import MagicMock, patch

import pytest

from pipeline.stages.video_production import _get_audio_duration


def test_get_audio_duration_success():
    """Verify that a valid duration is correctly parsed."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"format": {"duration": "123.45"}}).encode()

    with patch("subprocess.run", return_value=mock_result):
        duration = _get_audio_duration("test.mp3")
        assert duration == 123.45


def test_get_audio_duration_missing_format_key():
    """Verify RuntimeError is raised when 'format' key is missing."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    # JSON is valid but missing "format"
    mock_result.stdout = json.dumps({"other": "data"}).encode()

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="ffprobe returned unexpected output"):
            _get_audio_duration("test.mp3")


def test_get_audio_duration_missing_duration_key():
    """Verify RuntimeError is raised when 'duration' key is missing."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    # JSON has "format" but missing "duration"
    mock_result.stdout = json.dumps({"format": {}}).encode()

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="ffprobe returned unexpected output"):
            _get_audio_duration("test.mp3")


def test_get_audio_duration_invalid_type():
    """Verify RuntimeError is raised when duration is not convertible to float (e.g. None)."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    # "duration" is null -> float(None) raises TypeError
    mock_result.stdout = json.dumps({"format": {"duration": None}}).encode()

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="ffprobe returned unexpected output"):
            _get_audio_duration("test.mp3")


def test_get_audio_duration_invalid_json():
    """Verify JSONDecodeError bubbles up when output is not valid JSON."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = b"invalid-json"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(json.JSONDecodeError):
            _get_audio_duration("test.mp3")


def test_get_audio_duration_invalid_value():
    """Verify ValueError bubbles up when duration string is not a number."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    # "duration" is "not-a-number" -> float("not-a-number") raises ValueError
    mock_result.stdout = json.dumps({"format": {"duration": "not-a-number"}}).encode()

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(ValueError):
            _get_audio_duration("test.mp3")
