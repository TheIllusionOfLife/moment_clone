"""Tests for pipeline/stages/voice_memo.py."""

from pipeline.stages.voice_memo import run_voice_memo


def _make_session(voice_memo_url=None):
    """Return a minimal fake CookingSession-like object."""

    class FakeSession:
        id = 1
        voice_memo_url = None

    obj = FakeSession()
    obj.voice_memo_url = voice_memo_url
    return obj


def _make_dish():
    class FakeDish:
        id = 1
        name_ja = "チャーハン"

    return FakeDish()


class TestEarlyReturn:
    def test_early_return_when_no_voice_memo(self, mocker):
        """Session with voice_memo_url=None returns empty result immediately."""
        mocker.patch(
            "pipeline.stages.voice_memo.get_session_with_dish",
            return_value=(_make_session(voice_memo_url=None), _make_dish()),
        )
        update_mock = mocker.patch("pipeline.stages.voice_memo.update_session_fields")

        result = run_voice_memo(1)

        assert result == {"voice_transcript": "", "structured_input": {}}
        update_mock.assert_not_called()

    def test_early_return_when_empty_voice_memo(self, mocker):
        """Session with voice_memo_url='' returns empty result immediately."""
        mocker.patch(
            "pipeline.stages.voice_memo.get_session_with_dish",
            return_value=(_make_session(voice_memo_url=""), _make_dish()),
        )
        update_mock = mocker.patch("pipeline.stages.voice_memo.update_session_fields")

        result = run_voice_memo(1)

        assert result == {"voice_transcript": "", "structured_input": {}}
        update_mock.assert_not_called()


class TestSuccessPath:
    def test_run_voice_memo_success(self, mocker):
        """Mock GCS, STT, and Gemini; verify transcript and structured_input are persisted and returned."""
        session = _make_session(voice_memo_url="sessions/1/voice.m4a")
        dish = _make_dish()
        mocker.patch(
            "pipeline.stages.voice_memo.get_session_with_dish",
            return_value=(session, dish),
        )
        update_mock = mocker.patch("pipeline.stages.voice_memo.update_session_fields")

        # Mock GCS download
        mock_gcs_client = mocker.MagicMock()
        mock_bucket = mocker.MagicMock()
        mock_blob = mocker.MagicMock()
        mock_gcs_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mocker.patch("pipeline.stages.voice_memo.storage.Client", mock_gcs_client)

        # Mock STT
        mock_stt_result = mocker.MagicMock()
        mock_stt_result.results = [
            mocker.MagicMock(alternatives=[mocker.MagicMock(transcript="炒飯がうまく焼けました")]),
        ]
        mock_stt_client = mocker.MagicMock()
        mock_stt_client.return_value.recognize.return_value = mock_stt_result
        mocker.patch("pipeline.stages.voice_memo.speech.SpeechClient", mock_stt_client)

        # Mock Gemini
        structured = {"taste": 4, "appearance": 3, "texture": 4, "aroma": 5}
        mock_gemini_response = mocker.MagicMock()
        mock_gemini_response.text = '{"taste": 4, "appearance": 3, "texture": 4, "aroma": 5}'
        mock_gemini_client = mocker.MagicMock()
        mock_gemini_client.return_value.models.generate_content.return_value = mock_gemini_response
        mocker.patch("pipeline.stages.voice_memo.genai.Client", mock_gemini_client)

        result = run_voice_memo(1)

        assert result["voice_transcript"] == "炒飯がうまく焼けました"
        assert result["structured_input"] == structured
        update_mock.assert_called_once_with(
            1,
            voice_transcript="炒飯がうまく焼けました",
            structured_input=structured,
        )


class TestGeminiParseError:
    def test_run_voice_memo_gemini_parse_error(self, mocker):
        """If Gemini returns non-JSON, structured_input defaults to {} and result is still persisted."""
        session = _make_session(voice_memo_url="sessions/1/voice.m4a")
        dish = _make_dish()
        mocker.patch(
            "pipeline.stages.voice_memo.get_session_with_dish",
            return_value=(session, dish),
        )
        update_mock = mocker.patch("pipeline.stages.voice_memo.update_session_fields")

        # Mock GCS
        mock_gcs_client = mocker.MagicMock()
        mock_bucket = mocker.MagicMock()
        mock_blob = mocker.MagicMock()
        mock_gcs_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mocker.patch("pipeline.stages.voice_memo.storage.Client", mock_gcs_client)

        # Mock STT
        mock_stt_result = mocker.MagicMock()
        mock_stt_result.results = [
            mocker.MagicMock(alternatives=[mocker.MagicMock(transcript="テスト")]),
        ]
        mock_stt_client = mocker.MagicMock()
        mock_stt_client.return_value.recognize.return_value = mock_stt_result
        mocker.patch("pipeline.stages.voice_memo.speech.SpeechClient", mock_stt_client)

        # Mock Gemini returning non-JSON
        mock_gemini_response = mocker.MagicMock()
        mock_gemini_response.text = "This is not valid JSON at all."
        mock_gemini_client = mocker.MagicMock()
        mock_gemini_client.return_value.models.generate_content.return_value = mock_gemini_response
        mocker.patch("pipeline.stages.voice_memo.genai.Client", mock_gemini_client)

        result = run_voice_memo(1)

        assert result["voice_transcript"] == "テスト"
        assert result["structured_input"] == {}
        update_mock.assert_called_once_with(
            1,
            voice_transcript="テスト",
            structured_input={},
        )
