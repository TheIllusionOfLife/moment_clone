from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.auth import get_current_user
from backend.core.database import get_async_session


@pytest.fixture()
def client(app, async_engine, user):
    async def override_get_async_session():
        async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with async_session_factory() as session:
            yield session

    def override_auth():
        return user

    app.dependency_overrides[get_async_session] = override_get_async_session
    app.dependency_overrides[get_current_user] = override_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_upload_malformed_video_rejected(client, cooking_session):
    """
    Test that a text file masquerading as an MP4 is REJECTED.
    This confirms the fix for file content validation.
    """
    # Text content, not a valid MP4
    malformed_content = b"This is not a video file."

    with (
        patch("backend.routers.sessions.upload_file", new_callable=AsyncMock) as mock_upload,
        patch("backend.routers.sessions.send_video_uploaded", new_callable=AsyncMock),
        patch("backend.routers.sessions.generate_signed_url", new_callable=AsyncMock) as mock_sign,
    ):
        mock_upload.return_value = "sessions/1/raw_video_abc.mp4"
        mock_sign.return_value = "https://storage.example.com/signed"

        resp = client.post(
            f"/api/sessions/{cooking_session.id}/upload/",
            files={"video": ("fake_video.mp4", malformed_content, "video/mp4")},
        )

    # Expect 422 Unprocessable Entity due to invalid signature
    assert resp.status_code == 422
    assert "Invalid video format" in resp.json()["detail"]
