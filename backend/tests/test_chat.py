"""Tests for chat pagination bounds."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.core.auth import get_current_user
from backend.core.database import get_session
from backend.models.chat import ChatRoom


@pytest.fixture()
def chatroom(db, user):
    room = ChatRoom(user_id=user.id, room_type="coaching")
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@pytest.fixture()
def client(app, engine, user, chatroom):
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


def test_page_size_above_max_rejected(client):
    resp = client.get("/api/chat/rooms/coaching/messages/?page_size=101")
    assert resp.status_code == 422


def test_page_size_at_max_accepted(client):
    resp = client.get("/api/chat/rooms/coaching/messages/?page_size=100")
    assert resp.status_code == 200


def test_page_zero_rejected(client):
    resp = client.get("/api/chat/rooms/coaching/messages/?page=0")
    assert resp.status_code == 422


def test_page_size_zero_rejected(client):
    resp = client.get("/api/chat/rooms/coaching/messages/?page_size=0")
    assert resp.status_code == 422


def test_default_pagination_accepted(client):
    resp = client.get("/api/chat/rooms/coaching/messages/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 50
