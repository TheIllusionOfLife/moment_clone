"""Stage 0 — Voice Memo transcription and entity extraction."""

import tempfile

from google import genai
from google.cloud import speech, storage  # type: ignore[attr-defined]

from backend.core.settings import settings
from pipeline.stages.db_helpers import (
    _parse_json_response,
    get_session_with_dish,
    update_session_fields,
)


def run_voice_memo(session_id: int) -> dict:
    """Transcribe voice memo and extract structured self-assessment via Gemini.

    Returns: {"voice_transcript": str, "structured_input": dict}
    """
    session, dish = get_session_with_dish(session_id)

    if not session.voice_memo_url:
        return {"voice_transcript": "", "structured_input": {}}

    # Download audio from GCS to a temp file
    gcs_client = storage.Client()
    bucket = gcs_client.bucket(settings.GCS_BUCKET)
    blob = bucket.blob(session.voice_memo_url)

    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=True) as tmp:
        blob.download_to_filename(tmp.name)
        tmp_path = tmp.name

        # Google STT — ja-JP
        stt_client = speech.SpeechClient()
        with open(tmp_path, "rb") as f:
            audio = speech.RecognitionAudio(content=f.read())
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
            language_code="ja-JP",
        )
        response = stt_client.recognize(config=config, audio=audio)
        transcript = " ".join(
            r.alternatives[0].transcript for r in response.results if r.alternatives
        )

    # Gemini entity extraction
    gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = (
        f"以下の料理自己評価の音声テキストから、味・見た目・食感・香りの評価（1〜5点）と"
        f"ユーザーの自己評価を抽出し、JSON形式で返してください。\n\n"
        f"テキスト: <transcript>\n{transcript}\n</transcript>\n\n"
        f"出力形式例:\n"
        f'{{"taste": 4, "appearance": 3, "texture": 4, "aroma": 5, "self_assessment": "..."}}'
    )
    gemini_response = gemini_client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )

    try:
        structured_input = _parse_json_response(gemini_response.text or "")
    except Exception:
        structured_input = {}

    update_session_fields(
        session_id,
        voice_transcript=transcript,
        structured_input=structured_input,
    )
    return {"voice_transcript": transcript, "structured_input": structured_input}
