"""Tests for Clerk webhook handler: signature verification and idempotency."""

import json
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import Session, select

from backend.core.database import get_async_session
from backend.models.chat import ChatRoom
from backend.models.user import User


@pytest.fixture()
def client(app, async_engine):
    async def override_get_async_session():
        async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with async_session_factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_get_async_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _svix_headers(svix_id: str = "msg_001") -> dict:
    return {
        "svix-id": svix_id,
        "svix-timestamp": str(int(time.time())),
        "svix-signature": "v1,fakesig",
    }


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def test_invalid_signature_returns_400(client):
    with patch("backend.routers.auth.Webhook") as MockWebhook:
        from svix.webhooks import WebhookVerificationError

        MockWebhook.return_value.verify.side_effect = WebhookVerificationError("bad sig")
        resp = client.post(
            "/api/webhooks/clerk/",
            content=b'{"type":"user.created"}',
            headers=_svix_headers(),
        )
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# user.created event
# ---------------------------------------------------------------------------


def test_user_created_inserts_user_and_chatrooms(client, engine):
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_clerk_new",
            "email_addresses": [{"id": "ea_1", "email_address": "new@example.com"}],
            "primary_email_address_id": "ea_1",
            "first_name": "New",
        },
    }
    body = json.dumps(payload).encode()

    with patch("backend.routers.auth.Webhook") as MockWebhook:
        MockWebhook.return_value.verify.return_value = None  # signature passes
        resp = client.post(
            "/api/webhooks/clerk/",
            content=body,
            headers={**_svix_headers("msg_new_001"), "Content-Type": "application/json"},
        )

    assert resp.status_code == 200

    with Session(engine) as db:
        user = db.exec(select(User).where(User.clerk_user_id == "user_clerk_new")).first()
        assert user is not None
        assert user.email == "new@example.com"
        rooms = db.exec(select(ChatRoom).where(ChatRoom.user_id == user.id)).all()
        assert {r.room_type for r in rooms} == {"coaching", "cooking_videos"}


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_duplicate_svix_id_skipped(client, engine):
    """Same svix-id processed twice -> second call returns early, no duplicate rows."""
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_idem_test",
            "email_addresses": [{"id": "ea_2", "email_address": "idem@example.com"}],
            "primary_email_address_id": "ea_2",
            "first_name": "Idem",
        },
    }
    body = json.dumps(payload).encode()
    headers = {**_svix_headers("msg_idem_001"), "Content-Type": "application/json"}

    with patch("backend.routers.auth.Webhook") as MockWebhook:
        MockWebhook.return_value.verify.return_value = None
        client.post("/api/webhooks/clerk/", content=body, headers=headers)
        resp = client.post("/api/webhooks/clerk/", content=body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "already_processed"

    with Session(engine) as db:
        users = db.exec(select(User).where(User.clerk_user_id == "user_idem_test")).all()
        assert len(users) == 1

        from backend.models.webhook_event import WebhookEvent

        events = db.exec(select(WebhookEvent).where(WebhookEvent.id == "msg_idem_001")).all()
        assert len(events) == 1


# ---------------------------------------------------------------------------
# Race condition / IntegrityError handling
# ---------------------------------------------------------------------------


def test_user_created_concurrent_race_returns_200(client, engine):
    """Concurrent webhook: insert fails with IntegrityError, user found after rollback -> 200."""
    # Pre-insert the user so the re-query after rollback finds them.
    with Session(engine) as other_db:
        other_db.add(
            User(clerk_user_id="user_race_id", email="race@example.com", first_name="Race")
        )
        other_db.commit()

    payload = {
        "type": "user.created",
        "data": {
            "id": "user_race_id",
            "email_addresses": [{"id": "ea_1", "email_address": "race@example.com"}],
            "primary_email_address_id": "ea_1",
            "first_name": "Race",
        },
    }
    body = json.dumps(payload).encode()

    # The async webhook will find the existing user and skip insert.
    with patch("backend.routers.auth.Webhook") as MockWebhook:
        MockWebhook.return_value.verify.return_value = None
        resp = client.post(
            "/api/webhooks/clerk/",
            content=body,
            headers={**_svix_headers("msg_race_001"), "Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_user_created_unrelated_integrity_error_reraises(app, async_engine):
    """Non-duplicate IntegrityError (genuine DB failure) is re-raised -> 500."""
    from unittest.mock import MagicMock

    payload = {
        "type": "user.created",
        "data": {
            "id": "user_err_id",
            "email_addresses": [{"id": "ea_2", "email_address": "err@example.com"}],
            "primary_email_address_id": "ea_2",
            "first_name": "Err",
        },
    }
    body = json.dumps(payload).encode()

    call_count = [0]

    async def override_get_async_session():
        async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with async_session_factory() as session:
            original_execute = session.execute
            original_flush = session.flush

            async def patched_execute(stmt, *args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    # First execute (the "existing" check) returns None
                    mock_result = MagicMock()
                    mock_result.scalars.return_value.first.return_value = None
                    return mock_result
                return await original_execute(stmt, *args, **kwargs)

            async def patched_flush(*args, **kwargs):
                # Check if there are pending User objects
                if any(isinstance(obj, User) for obj in session.new):
                    raise SAIntegrityError(None, None, Exception("foreign key constraint"))
                return await original_flush(*args, **kwargs)

            session.execute = patched_execute
            session.flush = patched_flush
            yield session

    app.dependency_overrides[get_async_session] = override_get_async_session

    with patch("backend.routers.auth.Webhook") as MockWebhook:
        MockWebhook.return_value.verify.return_value = None
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/api/webhooks/clerk/",
                content=body,
                headers={
                    **_svix_headers("msg_err_001"),
                    "Content-Type": "application/json",
                },
            )

    assert resp.status_code == 500
