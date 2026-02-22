"""Stage 1 — Video analysis via Gemini multimodal structured prompt."""

import tempfile
import time

from google import genai
from google.cloud import storage  # type: ignore[attr-defined]
from google.genai import types

from backend.core.settings import settings
from pipeline.stages.db_helpers import (
    _parse_json_response,
    get_session_with_dish,
    update_session_fields,
)

_REQUIRED_KEYS = {"cooking_events", "key_moment_timestamp", "key_moment_seconds", "diagnosis"}


def run_video_analysis(session_id: int) -> dict:
    """Analyse the cooking video with Gemini and persist the result.

    Returns: {cooking_events, key_moment_timestamp, key_moment_seconds, diagnosis}
    """
    session, dish = get_session_with_dish(session_id)

    # Download raw video from GCS to a temp directory
    gcs_client = storage.Client()
    bucket = gcs_client.bucket(settings.GCS_BUCKET)
    blob = bucket.blob(session.raw_video_url)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_video_path = f"{tmp_dir}/video.mp4"
        blob.download_to_filename(tmp_video_path)

        # Upload to Gemini File API
        gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        uploaded_file = gemini_client.files.upload(file=tmp_video_path)  # type: ignore[misc]

    if uploaded_file.uri is None:
        raise RuntimeError("Gemini file upload returned no URI")
    if uploaded_file.name is None:
        raise RuntimeError("Gemini file upload returned no name")

    # Wait for the file to become ACTIVE (video processing can take a few seconds)
    for _ in range(30):
        file_info = gemini_client.files.get(name=uploaded_file.name)
        state = getattr(file_info.state, "name", str(file_info.state))
        if state == "ACTIVE":
            break
        if state == "FAILED":
            raise RuntimeError(f"Gemini file processing failed: {file_info.name}")
        time.sleep(2)
    else:
        raise RuntimeError("Gemini file did not become ACTIVE within 60 seconds")

    try:
        dish_name = session.custom_dish_name or dish.name_ja
        part = types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="video/mp4")
        prompt = (
            f"あなたは料理コーチです。この動画に映っている調理の様子をそのまま観察し、JSON形式で回答してください。\n"
            f"ユーザーが練習しようとしている料理は「{dish_name}」ですが、動画に映っている内容を忠実に分析してください。\n\n"
            f"以下の形式で回答してください:\n"
            f"{{\n"
            f'  "cooking_events": ["動画で実際に観察した調理イベントのリスト（見たままを記述）"],\n'
            f'  "key_moment_timestamp": "最重要ポイントの時刻 (例: 00:02:30)",\n'
            f'  "key_moment_seconds": 150,\n'
            f'  "diagnosis": "動画で実際に観察した内容に基づく診断と改善点"\n'
            f"}}"
        )
        response = gemini_client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[part, prompt],
        )
    finally:
        gemini_client.files.delete(name=uploaded_file.name)

    result = _parse_json_response(response.text or "")

    missing = _REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"Gemini response missing required keys: {missing}")

    update_session_fields(session_id, video_analysis=result)
    return result
