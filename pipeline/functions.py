"""Inngest durable AI coaching pipeline.

Each stage is a discrete step.run() — Inngest handles per-step retries,
observability (waterfall view with per-step I/O), and deduplication.

Stages:
  0: Voice memo STT + entity extraction  (optional)
  1: Video analysis                       (Gemini, single-agent structured)
  2: RAG                                  (Supabase pgvector)
  3a: Coaching text → deliver to chat    (~2–3 min from upload)
  3b: Narration script
  4: Video production (TTS + FFmpeg)     (~5–10 min from upload)
"""

import asyncio
import logging

import inngest

from backend.services.inngest_client import inngest_client
from pipeline.stages.coaching_script import run_coaching_script
from pipeline.stages.narration_script import run_narration_script
from pipeline.stages.rag import run_rag
from pipeline.stages.video_analysis import run_video_analysis
from pipeline.stages.video_production import run_video_production
from pipeline.stages.voice_memo import run_voice_memo

logger = logging.getLogger(__name__)


@inngest_client.create_function(  # type: ignore[arg-type, return-value]
    fn_id="cooking-pipeline",
    trigger=inngest.TriggerEvent(event="video/uploaded"),
    retries=4,
    concurrency=[inngest.Concurrency(key="event.data.user_id", limit=1)],
)
async def cooking_pipeline(ctx: inngest.Context, step: inngest.Step) -> None:
    # Validate event payload early — malformed events should not burn all retries.
    session_id = ctx.event.data.get("session_id")
    if not isinstance(session_id, int):
        print(f"ERROR: cooking-pipeline received invalid session_id: {session_id!r}")
        return

    user_id = ctx.event.data.get("user_id")
    if not isinstance(user_id, int):
        print(f"ERROR: cooking-pipeline received invalid user_id: {user_id!r}")
        return

    # Idempotency guard: use SELECT FOR UPDATE to prevent concurrent invocations
    # from both proceeding past this check for the same session.
    def _check_and_set_processing_sync() -> bool:
        from sqlmodel import Session as DBSession
        from sqlmodel import select

        from backend.core.database import get_engine
        from backend.models.session import CookingSession

        with DBSession(get_engine()) as db:
            cooking_session = db.exec(
                select(CookingSession).where(CookingSession.id == session_id).with_for_update()
            ).first()
            if cooking_session is None:
                return False
            if cooking_session.status not in ("uploaded", "failed"):
                return False
            cooking_session.status = "processing"
            db.add(cooking_session)
            db.commit()
        return True

    async def _check_and_set_processing() -> bool:
        try:
            return await asyncio.to_thread(_check_and_set_processing_sync)
        except Exception:
            logger.exception("PIPELINE ERROR [session=%s] check-and-set-processing", session_id)
            raise

    should_proceed: bool = await step.run("check-and-set-processing", _check_and_set_processing)  # type: ignore[arg-type, assignment]
    if not should_proceed:
        return

    def _set_terminal_status_sync(new_status: str, error: str | None = None) -> None:
        from sqlmodel import Session as DBSession

        from backend.core.database import get_engine
        from backend.models.session import CookingSession

        with DBSession(get_engine()) as db:
            cooking_session = db.get(CookingSession, session_id)
            if cooking_session:
                cooking_session.status = new_status
                # Always overwrite pipeline_error: set message on failure, clear on success.
                cooking_session.pipeline_error = error or ""
                db.add(cooking_session)
                db.commit()

    async def _set_terminal_status(new_status: str, error: str | None = None) -> None:
        try:
            await asyncio.to_thread(_set_terminal_status_sync, new_status, error)
        except Exception:
            logger.exception(
                "PIPELINE ERROR [session=%s] set-terminal-status(%s)", session_id, new_status
            )
            raise

    # Async wrappers: each stage runs in a thread (blocking I/O) and logs any
    # exception BEFORE the Inngest SDK's except-clause swallows it silently.

    async def _stage_0() -> dict:
        try:
            return await asyncio.to_thread(run_voice_memo, session_id)
        except Exception:
            logger.exception("PIPELINE ERROR [session=%s] stage-0-voice-memo", session_id)
            raise

    async def _stage_1() -> dict:
        try:
            return await asyncio.to_thread(run_video_analysis, session_id)
        except Exception:
            logger.exception("PIPELINE ERROR [session=%s] stage-1-video-analysis", session_id)
            raise

    async def _stage_2() -> dict:
        try:
            return await asyncio.to_thread(run_rag, session_id)
        except Exception:
            logger.exception("PIPELINE ERROR [session=%s] stage-2-rag", session_id)
            raise

    async def _stage_3a(ctx: dict) -> dict:
        try:
            return await asyncio.to_thread(run_coaching_script, session_id, ctx)
        except Exception:
            logger.exception("PIPELINE ERROR [session=%s] stage-3a-coaching-text", session_id)
            raise

    async def _stage_3b(ctx: dict) -> dict:
        try:
            return await asyncio.to_thread(run_narration_script, session_id, ctx)
        except Exception:
            logger.exception("PIPELINE ERROR [session=%s] stage-3b-narration-script", session_id)
            raise

    async def _stage_4(script: dict) -> None:
        try:
            await asyncio.to_thread(run_video_production, session_id, script)
        except Exception:
            logger.exception("PIPELINE ERROR [session=%s] stage-4-video-production", session_id)
            raise

    # Stage 0 — Voice memo (optional, runs if voice_memo_url is set)
    await step.run("stage-0-voice-memo", _stage_0)  # type: ignore[arg-type]

    # Stage 1 — Video analysis (persists to DB; downstream stages read from there)
    await step.run("stage-1-video-analysis", _stage_1)  # type: ignore[arg-type]

    # Stage 2 — RAG (pgvector similarity search)
    retrieved_context: dict = await step.run("stage-2-rag", _stage_2)  # type: ignore[assignment, arg-type]

    # Stage 3a — Coaching text → posted to chat immediately
    coaching_text: dict = await step.run(  # type: ignore[assignment, arg-type]
        "stage-3a-coaching-text", lambda: _stage_3a(retrieved_context)
    )

    # Stage 3b — Narration script (feeds video production)
    narration_script: dict = await step.run(  # type: ignore[assignment, arg-type]
        "stage-3b-narration-script", lambda: _stage_3b(coaching_text)
    )

    # Stage 4 — TTS + FFmpeg video composition → GCS
    await step.run("stage-4-video-production", lambda: _stage_4(narration_script))  # type: ignore[arg-type]

    await step.run("mark-completed", lambda: _set_terminal_status("completed"))  # type: ignore[arg-type, return-value]
