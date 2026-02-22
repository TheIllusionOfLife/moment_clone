"""Tests for session upload validation and ownership."""

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


@pytest.fixture()
def other_client(app, async_engine, other_user):
    """Client authenticated as a different user."""

    async def override_get_async_session():
        async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with async_session_factory() as session:
            yield session

    def override_auth():
        return other_user

    app.dependency_overrides[get_async_session] = override_get_async_session
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


# ---------------------------------------------------------------------------
# Memo text endpoint
# ---------------------------------------------------------------------------


def test_save_memo_text_persists_transcript(client, cooking_session):
    """POST /memo-text/ stores voice_transcript directly (no audio upload needed)."""
    resp = client.post(
        f"/api/sessions/{cooking_session.id}/memo-text/",
        json={"text": "今日は火加減が難しかったです。"},
    )
    assert resp.status_code == 200
    assert resp.json()["voice_transcript"] == "今日は火加減が難しかったです。"


def test_save_memo_text_strips_whitespace(client, cooking_session):
    resp = client.post(
        f"/api/sessions/{cooking_session.id}/memo-text/",
        json={"text": "  スペースあり  "},
    )
    assert resp.status_code == 200
    assert resp.json()["voice_transcript"] == "スペースあり"


def test_save_memo_text_empty_string_rejected(client, cooking_session):
    resp = client.post(
        f"/api/sessions/{cooking_session.id}/memo-text/",
        json={"text": ""},
    )
    assert resp.status_code == 422


def test_save_memo_text_wrong_owner_returns_404(other_client, cooking_session):
    resp = other_client.post(
        f"/api/sessions/{cooking_session.id}/memo-text/",
        json={"text": "test"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Free dish (自由投稿) session creation
# ---------------------------------------------------------------------------


@pytest.fixture()
def free_dish(db):
    from backend.models.dish import Dish

    d = Dish(
        slug="free",
        name_ja="自由投稿",
        name_en="Free Choice",
        description_ja="好きな料理",
        order=99,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def test_create_free_session_requires_custom_dish_name(client, free_dish):
    """POST /api/sessions/ with dish_slug=free and no custom_dish_name returns 422."""
    resp = client.post("/api/sessions/", json={"dish_slug": "free"})
    assert resp.status_code == 422


def test_create_free_session_with_custom_name_succeeds(client, free_dish):
    resp = client.post(
        "/api/sessions/",
        json={"dish_slug": "free", "custom_dish_name": "鶏の唐揚げ"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["custom_dish_name"] == "鶏の唐揚げ"


def test_free_dish_allows_more_than_three_sessions(client, db, user, free_dish):
    """Free dish bypasses the 3-session cap."""
    from backend.models.session import CookingSession

    # Pre-create 3 sessions so the next would normally be blocked
    for n in range(1, 4):
        s = CookingSession(user_id=user.id, dish_id=free_dish.id, session_number=n)
        db.add(s)
    db.commit()

    resp = client.post(
        "/api/sessions/",
        json={"dish_slug": "free", "custom_dish_name": "4回目の料理"},
    )
    assert resp.status_code == 201
    assert resp.json()["session_number"] == 4


def test_non_free_dish_blocks_fourth_session(client, db, user, dish):
    """Non-free dishes still enforce the 3-session cap."""
    from backend.models.session import CookingSession

    for n in range(1, 4):
        s = CookingSession(user_id=user.id, dish_id=dish.id, session_number=n)
        db.add(s)
    db.commit()

    resp = client.post("/api/sessions/", json={"dish_slug": dish.slug})
    assert resp.status_code == 400
