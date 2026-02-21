"""Stage 4 — Video production.

Downloads raw video from GCS, runs Cloud TTS for part1/part2 narration, extracts
a 15-second key-moment clip with FFmpeg, composes the coaching video, uploads it
to GCS, and posts it to the user's coaching chat room.

Does NOT set status='completed' — that is handled by the mark-completed step in
pipeline/functions.py.
"""

import json as _json
import os
import subprocess
import tempfile

from google.cloud import storage, texttospeech
from sqlmodel import Session as DBSession

from backend.core.database import get_engine
from backend.core.settings import settings
from pipeline.stages.db_helpers import (
    get_coaching_room,
    get_session_with_dish,
    post_message,
    update_session_fields,
)


def _run_ffmpeg(args: list[str]) -> None:
    """Run FFmpeg; re-raise as RuntimeError with stderr on non-zero exit."""
    result = subprocess.run(
        ["ffmpeg", "-y", *args],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed (exit {result.returncode}): {result.stderr.decode()}")


def _get_audio_duration(audio_path: str) -> float:
    """Return duration in seconds of an audio file via ffprobe."""
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            audio_path,
        ],
        capture_output=True,
        check=True,
    )
    return float(_json.loads(probe.stdout)["format"]["duration"])


def _synthesize_tts(tts_client: texttospeech.TextToSpeechClient, text: str, out_path: str) -> None:
    """Synthesize text to MP3 and write to out_path."""
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=settings.TTS_LANGUAGE,
        name=settings.TTS_VOICE,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
    )
    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    with open(out_path, "wb") as f:
        f.write(response.audio_content)


def run_video_production(session_id: int, narration_script: dict) -> str:
    """Compose coaching video from TTS audio + raw video clip and upload to GCS.

    Returns:
        GCS object path, e.g. 'sessions/42/coaching_video.mp4'
    """
    session, dish = get_session_with_dish(session_id)

    gcs_client = storage.Client()
    tts_client = texttospeech.TextToSpeechClient()

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_video_path = os.path.join(tmpdir, "raw.mp4")
        part1_audio_path = os.path.join(tmpdir, "part1.mp3")
        part2_audio_path = os.path.join(tmpdir, "part2.mp3")
        intro_segment_path = os.path.join(tmpdir, "intro_segment.mp4")
        key_moment_clip_path = os.path.join(tmpdir, "key_moment_clip.mp4")
        key_moment_segment_path = os.path.join(tmpdir, "key_moment_segment.mp4")
        concat_list_path = os.path.join(tmpdir, "concat_list.txt")
        coaching_video_path = os.path.join(tmpdir, "coaching_video.mp4")

        # Step 1: Download raw video from GCS.
        blob = gcs_client.bucket(settings.GCS_BUCKET).blob(session.raw_video_url)
        blob.download_to_filename(raw_video_path)

        # Step 2: TTS for part1 and part2.
        _synthesize_tts(tts_client, narration_script["part1"], part1_audio_path)
        _synthesize_tts(tts_client, narration_script["part2"], part2_audio_path)

        # Step 3: Extract 15-second clip at key_moment_seconds.
        key_moment = (session.video_analysis or {}).get("key_moment_seconds", 0)
        _run_ffmpeg(
            [
                "-ss",
                str(key_moment),
                "-i",
                raw_video_path,
                "-t",
                "15",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                key_moment_clip_path,
            ]
        )

        # Step 4: Compose intro segment (black screen + part1 audio).
        part1_duration = _get_audio_duration(part1_audio_path)
        _run_ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=black:s=1280x720:r=30:d={part1_duration}",
                "-i",
                part1_audio_path,
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-t",
                str(part1_duration),
                "-shortest",
                intro_segment_path,
            ]
        )

        # Step 5: Compose key-moment segment (clip + part2 audio).
        part2_duration = _get_audio_duration(part2_audio_path)
        _run_ffmpeg(
            [
                "-i",
                key_moment_clip_path,
                "-i",
                part2_audio_path,
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-t",
                str(part2_duration),
                "-shortest",
                key_moment_segment_path,
            ]
        )

        # Step 6: Concatenate intro + key-moment via concat demuxer.
        with open(concat_list_path, "w") as f:
            f.write(f"file '{intro_segment_path}'\n")
            f.write(f"file '{key_moment_segment_path}'\n")

        _run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list_path,
                "-c",
                "copy",
                coaching_video_path,
            ]
        )

        # Step 7: Upload coaching video to GCS.
        gcs_path = f"sessions/{session_id}/coaching_video.mp4"
        with open(coaching_video_path, "rb") as f:
            gcs_client.bucket(settings.GCS_BUCKET).blob(gcs_path).upload_from_file(
                f, content_type="video/mp4"
            )

    # Step 8: Post coaching video message to coaching chat room.
    with DBSession(get_engine()) as db:
        coaching_room = get_coaching_room(session.user_id, db)
        post_message(
            coaching_room.id,
            "ai",
            session_id,
            video_gcs_path=gcs_path,
            db=db,
        )

    # Step 9: Persist coaching_video_gcs_path on session.
    update_session_fields(session_id, coaching_video_gcs_path=gcs_path)

    return gcs_path
