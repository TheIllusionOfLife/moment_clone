"""Tests for security validation on file uploads."""

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

def test_upload_video_fake_content_rejected(client, cooking_session):
    """
    Test that a file with a valid video MIME type but invalid content (e.g., text)
    is rejected with 422 Unprocessable Entity due to magic byte mismatch.
    """
    # Create a fake file: valid extension/MIME, but content is just text
    fake_content = b"This is definitely not a video file."

    resp = client.post(
        f"/api/sessions/{cooking_session.id}/upload/",
        files={"video": ("fake.mp4", fake_content, "video/mp4")},
    )

    assert resp.status_code == 422
    assert "magic bytes mismatch" in resp.json()["detail"]

def test_upload_video_valid_content_accepted(client, cooking_session):
    """
    Test that a file with valid MP4 magic bytes is accepted.
    """
    # Minimal MP4 signature: ....ftyp....
    # filetype checks for 'ftyp' at offset 4
    # offset 0-3: size (00 00 00 18) = 24 bytes
    # offset 4-7: 'ftyp'
    # offset 8-11: 'mp42' (major brand)
    # offset 12-15: version
    # ...

    # Construct a minimal header that filetype recognizes as video/mp4
    valid_header = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16
    content = valid_header + b"\x00" * 1024 # Add some padding

    with (
        patch("backend.routers.sessions.upload_file", new_callable=AsyncMock) as mock_upload,
        patch("backend.routers.sessions.send_video_uploaded", new_callable=AsyncMock),
        patch("backend.routers.sessions.generate_signed_url", new_callable=AsyncMock) as mock_sign,
    ):
        mock_upload.return_value = "sessions/1/raw_video_valid.mp4"
        mock_sign.return_value = "https://storage.example.com/signed"

        resp = client.post(
            f"/api/sessions/{cooking_session.id}/upload/",
            files={"video": ("real.mp4", content, "video/mp4")},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "uploaded"
