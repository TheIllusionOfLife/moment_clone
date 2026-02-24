from unittest.mock import AsyncMock, patch

import inngest
import pytest

from backend.services.inngest_client import send_video_uploaded


@pytest.mark.asyncio
async def test_send_video_uploaded():
    """Test that send_video_uploaded correctly creates an event and sends it."""
    # Mock the inngest_client.send method
    # We patch the instance's send method on the module where it is defined/imported.
    # backend.services.inngest_client.inngest_client is the instance.
    with patch("backend.services.inngest_client.inngest_client.send", new_callable=AsyncMock) as mock_send:
        session_id = 123
        user_id = 456

        await send_video_uploaded(session_id, user_id)

        assert mock_send.await_count == 1

        # Check arguments
        call_args = mock_send.await_args
        event = call_args[0][0]

        assert isinstance(event, inngest.Event)
        assert event.name == "video/uploaded"
        assert event.data == {"session_id": session_id, "user_id": user_id}
