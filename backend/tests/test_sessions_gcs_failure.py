import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from backend.models.session import CookingSession
from backend.routers.sessions import _session_to_dict


@pytest.mark.asyncio
async def test_session_to_dict_handles_gcs_failure():
    # Mock session
    session = CookingSession(
        user_id=uuid.uuid4(),
        dish_id=1,
        session_number=1,
        raw_video_url="sessions/1/video.mp4",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.id = 1

    # Mock generate_signed_url to return None (simulating failure caught in service)
    with patch("backend.routers.sessions.generate_signed_url", new_callable=AsyncMock) as mock_sign:
        mock_sign.return_value = None

        result = await _session_to_dict(session)

        assert result["raw_video_url"] is None

@pytest.mark.asyncio
async def test_session_to_dict_suppresses_gcs_exception():
    # This test verifies that if generate_signed_url RAISES an exception (e.g. unexpected error),
    # _session_to_dict suppresses it and returns None for the URL.
    session = CookingSession(
        user_id=uuid.uuid4(),
        dish_id=1,
        session_number=1,
        raw_video_url="sessions/1/video.mp4",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.id = 1

    with patch("backend.routers.sessions.generate_signed_url", new_callable=AsyncMock) as mock_sign:
        mock_sign.side_effect = Exception("Boom!")

        result = await _session_to_dict(session)

        # Should suppress exception and return None
        assert result["raw_video_url"] is None
