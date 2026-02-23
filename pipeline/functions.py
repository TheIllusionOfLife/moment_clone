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
from collections.abc import Callable
from typing import Any

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
async def cooking_pipeline(ctx: inngest.Context) -> None:
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
    async def _run_stage(stage_name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception:
            logger.exception("PIPELINE ERROR [session=%s] %s", session_id, stage_name)
            raise

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

    should_proceed: bool = await ctx.step.run(  # type: ignore[arg-type, assignment]
        "check-and-set-processing",
        lambda: _run_stage("check-and-set-processing", _check_and_set_processing_sync),
    )
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

    try:
        # Stage 0 — Voice memo (optional, runs if voice_memo_url is set)
        await ctx.step.run(
            "stage-0-voice-memo",
            lambda: _run_stage("stage-0-voice-memo", run_voice_memo, session_id),
        )  # type: ignore[arg-type]

        # Stage 1 — Video analysis (persists to DB; downstream stages read from there)
        await ctx.step.run(
            "stage-1-video-analysis",
            lambda: _run_stage("stage-1-video-analysis", run_video_analysis, session_id),
        )  # type: ignore[arg-type]

        # Stage 2 — RAG (pgvector similarity search)
        retrieved_context: dict = await ctx.step.run(  # type: ignore[assignment, arg-type]
            "stage-2-rag",
            lambda: _run_stage("stage-2-rag", run_rag, session_id),
        )

        # Stage 3a — Coaching text → posted to chat immediately
        coaching_text: dict = await ctx.step.run(  # type: ignore[assignment, arg-type]
            "stage-3a-coaching-text",
            lambda: _run_stage(
                "stage-3a-coaching-text", run_coaching_script, session_id, retrieved_context
            ),
        )

        # Stage 3b — Narration script (feeds video production)
        narration_script: dict = await ctx.step.run(  # type: ignore[assignment, arg-type]
            "stage-3b-narration-script",
            lambda: _run_stage(
                "stage-3b-narration-script", run_narration_script, session_id, coaching_text
            ),
        )

        # Stage 4 — TTS + FFmpeg video composition → GCS
        await ctx.step.run(  # type: ignore[arg-type]
            "stage-4-video-production",
            lambda: _run_stage(
                "stage-4-video-production", run_video_production, session_id, narration_script
            ),
        )

        await ctx.step.run(  # type: ignore[arg-type, return-value]
            "mark-completed",
            lambda: _run_stage(
                "set-terminal-status(completed)", _set_terminal_status_sync, "completed"
            ),
        )
    except Exception as exc:
        # Stage wrappers already log the specific exception; here we persist the
        # failed status so the session doesn't stay stuck at "processing".
        # Wrap mark-failed so it cannot mask the original exception.
        error_msg = str(exc)
        try:
            await ctx.step.run(  # type: ignore[arg-type, return-value]
                "mark-failed",
                lambda: _run_stage(
                    "set-terminal-status(failed)",
                    _set_terminal_status_sync,
                    "failed",
                    error=error_msg,
                ),
            )
        except Exception:
            logger.exception(
                "PIPELINE ERROR [session=%s] mark-failed (secondary error — original exc below)",
                session_id,
            )
        raise  # always re-raise the original stage exception
