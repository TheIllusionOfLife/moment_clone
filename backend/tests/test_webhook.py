"""Tests for Clerk webhook handler: signature verification and idempotency."""

import json
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError as SAIntegrityError
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


# ---------------------------------------------------------------------------
# Race condition / IntegrityError handling
# ---------------------------------------------------------------------------


def test_user_created_concurrent_race_returns_200(client, engine):
    """Concurrent webhook: insert fails with IntegrityError, user found after rollback → 200."""
    from unittest.mock import MagicMock

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

    # Patch Session.exec so the initial "existing" check returns None
    # (simulating the race: user doesn't exist at check time but does at flush time).
    # Real db.flush() will then raise IntegrityError against the pre-inserted row.
    original_exec = Session.exec
    exec_call_count = [0]

    def patched_exec(self: Session, statement, *args, **kwargs):  # type: ignore[misc]
        exec_call_count[0] += 1
        if exec_call_count[0] == 1:
            mock = MagicMock()
            mock.first.return_value = None
            return mock
        return original_exec(self, statement, *args, **kwargs)

    with patch("backend.routers.auth.Webhook") as MockWebhook:
        MockWebhook.return_value.verify.return_value = None
        with patch.object(Session, "exec", patched_exec):
            resp = client.post(
                "/api/webhooks/clerk/",
                content=body,
                headers={**_svix_headers("msg_race_001"), "Content-Type": "application/json"},
            )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_user_created_unrelated_integrity_error_reraises(app):
    """Non-duplicate IntegrityError (genuine DB failure) is re-raised → 500."""
    from unittest.mock import MagicMock

    from backend.models.user import User as UserModel

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

    original_exec = Session.exec
    exec_call_count = [0]

    def patched_exec(self: Session, statement, *args, **kwargs):  # type: ignore[misc]
        exec_call_count[0] += 1
        if exec_call_count[0] == 1:
            mock = MagicMock()
            mock.first.return_value = None
            return mock
        return original_exec(self, statement, *args, **kwargs)

    # Only raise IntegrityError when User objects are actually pending (the real insert),
    # not on autoflush calls on a clean session.
    # No user is pre-inserted, so the recovery re-query returns None → handler re-raises.
    original_flush = Session.flush

    def patched_flush(self: Session) -> None:
        if any(isinstance(obj, UserModel) for obj in self.new):
            raise SAIntegrityError(None, None, Exception("foreign key constraint"))
        return original_flush(self)

    with patch("backend.routers.auth.Webhook") as MockWebhook:
        MockWebhook.return_value.verify.return_value = None
        with patch.object(Session, "exec", patched_exec):
            with patch.object(Session, "flush", patched_flush):
                # raise_server_exceptions=False so unhandled exceptions return 500
                # instead of being re-raised through the test client.
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
