import inngest

from backend.core.settings import settings

inngest_client = inngest.Inngest(
    app_id="moment-clone",
    event_key=settings.INNGEST_EVENT_KEY or "local-dev-key",
    is_production=bool(settings.INNGEST_SIGNING_KEY),
)


async def send_video_uploaded(session_id: int) -> None:
    """Emit the video/uploaded event to kick off the AI coaching pipeline."""
    event = inngest.Event(
        name="video/uploaded",
        data={"session_id": session_id},
    )
    await inngest_client.send(event)
