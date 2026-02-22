import inngest

from backend.core.settings import settings

# Do NOT pass is_production here. Let the SDK auto-detect the mode:
#   - Local dev: set INNGEST_DEV=1 in .env → SDK uses Dev Server mode
#     (requests/steps are fetched from the local Inngest CLI, not api.inngest.com)
#   - Production: INNGEST_DEV is unset → SDK uses Cloud mode automatically
#
# Forcing is_production=True (the old behaviour) put the SDK into Cloud mode even
# during local dev. When request.use_api=True the SDK called
# https://api.inngest.com/v0/runs/{id}/batch which failed → silent HTTP 500.
inngest_client = inngest.Inngest(
    app_id="moment-clone",
    event_key=settings.INNGEST_EVENT_KEY or "local-dev-key",
    signing_key=settings.INNGEST_SIGNING_KEY or None,
)


async def send_video_uploaded(session_id: int, user_id: int) -> None:
    """Emit the video/uploaded event to kick off the AI coaching pipeline."""
    event = inngest.Event(
        name="video/uploaded",
        data={"session_id": session_id, "user_id": user_id},
    )
    await inngest_client.send(event)
