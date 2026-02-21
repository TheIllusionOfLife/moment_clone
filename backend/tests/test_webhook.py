"""Tests for Clerk webhook handler: signature verification and idempotency."""

import json
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.core.database import get_session
from backend.models.chat import ChatRoom
from backend.models.user import User


@pytest.fixture()
def client(app, engine):
    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
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
    """Same svix-id processed twice → second call returns early, no duplicate rows."""
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
