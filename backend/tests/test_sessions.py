"""Tests for session upload validation and ownership."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.core.auth import get_current_user
from backend.core.database import get_session


@pytest.fixture()
def client(app, engine, user):
    def override_get_session():
        with Session(engine) as session:
            yield session

    def override_auth():
        return user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def other_client(app, engine, other_user):
    """Client authenticated as a different user."""
    def override_get_session():
        with Session(engine) as session:
            yield session

    def override_auth():
        return other_user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# MIME type validation
# ---------------------------------------------------------------------------


def test_upload_video_invalid_mime_rejected(client, cooking_session):
    resp = client.post(
        f"/api/sessions/{cooking_session.id}/upload/",
        files={"video": ("clip.gif", b"GIF89a", "image/gif")},
    )
    assert resp.status_code == 422
    assert "image/gif" in resp.json()["detail"]


def test_upload_video_valid_mime_accepted(client, cooking_session):
    small_mp4 = b"\x00" * 100
    with (
        patch("backend.routers.sessions.upload_file", new_callable=AsyncMock) as mock_upload,
        patch("backend.routers.sessions.send_video_uploaded", new_callable=AsyncMock),
        patch("backend.routers.sessions.generate_signed_url", new_callable=AsyncMock) as mock_sign,
    ):
        mock_upload.return_value = "sessions/1/raw_video_abc.mp4"
        mock_sign.return_value = "https://storage.example.com/signed"
        resp = client.post(
            f"/api/sessions/{cooking_session.id}/upload/",
            files={"video": ("clip.mp4", small_mp4, "video/mp4")},
        )
    assert resp.status_code == 200


def test_upload_audio_invalid_mime_rejected(client, cooking_session):
    resp = client.post(
        f"/api/sessions/{cooking_session.id}/voice-memo/",
        files={"audio": ("note.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 422
    assert "text/plain" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Size validation
# ---------------------------------------------------------------------------


def test_upload_video_exceeds_limit_rejected(monkeypatch, client, cooking_session):
    """Uploading more than MAX_VIDEO_BYTES returns 422 (MAX_VIDEO_BYTES patched to 10 bytes)."""
    import backend.routers.sessions as sessions_module

    monkeypatch.setattr(sessions_module, "MAX_VIDEO_BYTES", 10)
    oversized = b"\x00" * 11
    resp = client.post(
        f"/api/sessions/{cooking_session.id}/upload/",
        files={"video": ("big.mp4", oversized, "video/mp4")},
    )
    assert resp.status_code == 422
    assert "500 MB" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Ownership check
# ---------------------------------------------------------------------------


def test_get_session_wrong_owner_returns_404(other_client, cooking_session):
    """Accessing another user's session must return 404, not 403."""
    resp = other_client.get(f"/api/sessions/{cooking_session.id}/")
    assert resp.status_code == 404


def test_get_session_owner_returns_200(client, cooking_session):
    resp = client.get(f"/api/sessions/{cooking_session.id}/")
    assert resp.status_code == 200
    assert resp.json()["id"] == cooking_session.id


# ---------------------------------------------------------------------------
# Ratings validation
# ---------------------------------------------------------------------------


def test_ratings_out_of_range_rejected(client, cooking_session):
    resp = client.patch(
        f"/api/sessions/{cooking_session.id}/ratings/",
        json={"appearance": 6, "taste": 3, "texture": 3, "aroma": 3},
    )
    assert resp.status_code == 422


def test_ratings_valid(client, cooking_session):
    resp = client.patch(
        f"/api/sessions/{cooking_session.id}/ratings/",
        json={"appearance": 4, "taste": 5, "texture": 3, "aroma": 2},
    )
    assert resp.status_code == 200
    assert resp.json()["self_ratings"]["appearance"] == 4
