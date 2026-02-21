"""Tests for pipeline/stages/video_analysis.py."""

import json

import pytest

from pipeline.stages.video_analysis import run_video_analysis


def _make_session(raw_video_url="sessions/1/raw.mp4"):
    class FakeSession:
        id = 1

    obj = FakeSession()
    obj.raw_video_url = raw_video_url
    return obj


def _make_dish():
    class FakeDish:
        id = 1
        name_ja = "チャーハン"

    return FakeDish()


VALID_ANALYSIS = {
    "cooking_events": ["高温で炒めた", "卵を先に投入"],
    "key_moment_timestamp": "00:02:30",
    "key_moment_seconds": 150,
    "diagnosis": "全体的に良かったが、火加減をもう少し強くすると良い",
}


def _mock_gcs(mocker):
    mock_gcs_client = mocker.MagicMock()
    mock_bucket = mocker.MagicMock()
    mock_blob = mocker.MagicMock()
    mock_gcs_client.return_value.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mocker.patch("pipeline.stages.video_analysis.storage.Client", mock_gcs_client)
    return mock_blob


def _mock_gemini(mocker, response_text: str):
    mock_uploaded_file = mocker.MagicMock()
    mock_uploaded_file.uri = "https://generativelanguage.googleapis.com/v1beta/files/abc123"
    mock_uploaded_file.name = "files/abc123"

    mock_gemini_client = mocker.MagicMock()
    mock_gemini_client.return_value.files.upload.return_value = mock_uploaded_file
    mock_gemini_client.return_value.models.generate_content.return_value = mocker.MagicMock(
        text=response_text
    )
    mocker.patch("pipeline.stages.video_analysis.genai.Client", mock_gemini_client)
    return mock_gemini_client


class TestSuccess:
    def test_run_video_analysis_success(self, mocker):
        """Mock GCS and Gemini; verify result keys and update_session_fields called."""
        mocker.patch(
            "pipeline.stages.video_analysis.get_session_with_dish",
            return_value=(_make_session(), _make_dish()),
        )
        update_mock = mocker.patch("pipeline.stages.video_analysis.update_session_fields")
        _mock_gcs(mocker)
        mock_gemini_client = _mock_gemini(mocker, json.dumps(VALID_ANALYSIS))

        result = run_video_analysis(1)

        assert result["cooking_events"] == VALID_ANALYSIS["cooking_events"]
        assert result["key_moment_timestamp"] == "00:02:30"
        assert result["key_moment_seconds"] == 150
        assert "診断" in result["diagnosis"] or result["diagnosis"]  # non-empty
        update_mock.assert_called_once_with(1, video_analysis=result)
        # Verify delete was called (cleanup)
        mock_gemini_client.return_value.files.delete.assert_called_once_with(name="files/abc123")


class TestFinallyCleanup:
    def test_run_video_analysis_file_deleted_on_error(self, mocker):
        """Even when generate_content raises, files.delete must be called (finally block)."""
        mocker.patch(
            "pipeline.stages.video_analysis.get_session_with_dish",
            return_value=(_make_session(), _make_dish()),
        )
        mocker.patch("pipeline.stages.video_analysis.update_session_fields")
        _mock_gcs(mocker)

        mock_uploaded_file = mocker.MagicMock()
        mock_uploaded_file.uri = "https://generativelanguage.googleapis.com/v1beta/files/abc123"
        mock_uploaded_file.name = "files/abc123"

        mock_gemini_client = mocker.MagicMock()
        mock_gemini_client.return_value.files.upload.return_value = mock_uploaded_file
        mock_gemini_client.return_value.models.generate_content.side_effect = RuntimeError(
            "API timeout"
        )
        mocker.patch("pipeline.stages.video_analysis.genai.Client", mock_gemini_client)

        with pytest.raises(RuntimeError, match="API timeout"):
            run_video_analysis(1)

        mock_gemini_client.return_value.files.delete.assert_called_once_with(name="files/abc123")


class TestMissingKey:
    def test_run_video_analysis_missing_key_raises(self, mocker):
        """JSON missing a required key raises ValueError."""
        mocker.patch(
            "pipeline.stages.video_analysis.get_session_with_dish",
            return_value=(_make_session(), _make_dish()),
        )
        mocker.patch("pipeline.stages.video_analysis.update_session_fields")
        _mock_gcs(mocker)

        incomplete = {
            "cooking_events": ["炒めた"],
            "key_moment_timestamp": "00:01:00",
            # missing key_moment_seconds and diagnosis
        }
        _mock_gemini(mocker, json.dumps(incomplete))

        with pytest.raises(ValueError):
            run_video_analysis(1)


class TestInvalidJson:
    def test_run_video_analysis_invalid_json_raises(self, mocker):
        """Non-JSON response from Gemini propagates as an exception."""
        mocker.patch(
            "pipeline.stages.video_analysis.get_session_with_dish",
            return_value=(_make_session(), _make_dish()),
        )
        mocker.patch("pipeline.stages.video_analysis.update_session_fields")
        _mock_gcs(mocker)
        _mock_gemini(mocker, "これはJSONではありません。普通のテキストです。")

        with pytest.raises(ValueError):
            run_video_analysis(1)
