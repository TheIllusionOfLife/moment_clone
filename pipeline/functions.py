"""Inngest durable AI coaching pipeline.

Each stage is a discrete step.run() — Inngest handles per-step retries,
observability (waterfall view with per-step I/O), and deduplication.

Stages (Phase 2 will fill these in):
  0: Voice memo STT + entity extraction  (optional)
  1: Video analysis                       (Gemini, single-agent structured)
  2: RAG                                  (Supabase pgvector)
  3a: Coaching text → deliver to chat    (~2–3 min from upload)
  3b: Narration script
  4: Video production (TTS + FFmpeg)     (~5–10 min from upload)
"""

import inngest

from backend.services.inngest_client import inngest_client


@inngest_client.create_function(
    fn_id="cooking-pipeline",
    trigger=inngest.TriggerEvent(event="video/uploaded"),
    retries=4,
)
async def cooking_pipeline(ctx: inngest.Context, step: inngest.Step) -> None:
    # Validate event payload early — malformed events should not burn all retries.
    session_id = ctx.event.data.get("session_id")
    if not isinstance(session_id, int):
        # Log and exit without retrying; nothing useful can be done without a valid ID.
        print(f"ERROR: cooking-pipeline received invalid session_id: {session_id!r}")
        return

    # Idempotency guard: use SELECT FOR UPDATE to prevent concurrent invocations
    # from both proceeding past this check for the same session.
    def _check_and_set_processing() -> bool:
        from sqlmodel import Session as DBSession
        from sqlmodel import select

        from backend.core.database import engine
        from backend.models.session import CookingSession

        with DBSession(engine) as db:
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

    should_proceed = await step.run("check-and-set-processing", _check_and_set_processing)
    if not should_proceed:
        return

    # Stage 0 — Voice memo (optional, runs if voice_memo_url is set)
    await step.run("stage-0-voice-memo", lambda: None)

    # Stage 1 — Video analysis
    await step.run("stage-1-video-analysis", lambda: None)

    # Stage 2 — RAG (pgvector similarity search)
    await step.run("stage-2-rag", lambda: None)

    # Stage 3a — Coaching text → posted to chat immediately
    await step.run("stage-3a-coaching-text", lambda: None)

    # Stage 3b — Narration script (feeds video production)
    await step.run("stage-3b-narration-script", lambda: None)

    # Stage 4 — TTS + FFmpeg video composition → GCS
    await step.run("stage-4-video-production", lambda: None)
