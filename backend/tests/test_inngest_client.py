from unittest.mock import AsyncMock, patch

import inngest
import pytest

from backend.services.inngest_client import send_video_uploaded


@pytest.mark.asyncio
async def test_send_video_uploaded_emits_event():
    """
    Test that send_video_uploaded correctly constructs an inngest.Event
    and sends it using the inngest_client.
    """
    # Patch the send method of the inngest_client instance in the module
    with patch("backend.services.inngest_client.inngest_client.send", new_callable=AsyncMock) as mock_send:
        session_id = 101
        user_id = 202

        await send_video_uploaded(session_id, user_id)

        # Verify the send method was called exactly once
        assert mock_send.call_count == 1

        # Verify the arguments passed to send
        call_args = mock_send.call_args
        event = call_args[0][0]  # The first positional argument should be the event

        # Check that the argument is indeed an inngest.Event
        assert isinstance(event, inngest.Event)

        # Verify the event's name and data payload
        assert event.name == "video/uploaded"
        assert event.data == {"session_id": session_id, "user_id": user_id}
