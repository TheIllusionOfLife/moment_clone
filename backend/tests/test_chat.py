"""Tests for chat endpoints including Q&A AI reply."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select

from backend.core.auth import get_current_user
from backend.core.database import get_async_session
from backend.models.chat import ChatRoom, Message
from backend.models.session import CookingSession


@pytest.fixture()
def chatroom(db, user):
    room = ChatRoom(user_id=user.id, room_type="coaching")
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@pytest.fixture()
def cooking_videos_room(db, user):
    room = ChatRoom(user_id=user.id, room_type="cooking_videos")
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@pytest.fixture()
def client(app, async_engine, user, chatroom):  # noqa: ARG001
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
def completed_session(db, user, dish):
    s = CookingSession(
        user_id=user.id,
        dish_id=dish.id,
        session_number=1,
        status="completed",
        coaching_text={
            "mondaiten": "水分が多すぎます",
            "skill": "水分管理",
            "next_action": "強火で炒める",
            "success_sign": "パラパラになる",
        },
        video_analysis={
            "diagnosis": "火力が弱く水分が残っている",
            "cooking_events": ["卵を割る", "ご飯を入れる"],
        },
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


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


# ---------------------------------------------------------------------------
# Chat Q&A — AI reply via BackgroundTasks
# ---------------------------------------------------------------------------


def test_send_message_coaching_room_triggers_background_task(
    app, async_engine, user, chatroom, mocker
):
    """Posting a user message in the coaching room queues an AI reply task."""
    mock_add_task = mocker.patch("fastapi.BackgroundTasks.add_task")

    async def override_get_async_session():
        async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with async_session_factory() as session:
            yield session

    def override_auth():
        return user

    app.dependency_overrides[get_async_session] = override_get_async_session
    app.dependency_overrides[get_current_user] = override_auth

    try:
        with TestClient(app) as c:
            resp = c.post(
                "/api/chat/rooms/coaching/messages/",
                json={"text": "チャーハンのコツを教えてください"},
            )
        assert resp.status_code == 201
        mock_add_task.assert_called_once()
        # First arg to add_task must be the _generate_coaching_reply coroutine function
        from backend.routers.chat import _generate_coaching_reply

        assert mock_add_task.call_args[0][0] is _generate_coaching_reply
    finally:
        app.dependency_overrides.clear()


def test_send_message_cooking_videos_room_no_ai_reply(
    app,
    async_engine,
    user,
    cooking_videos_room,
    mocker,
):
    """Posting to cooking_videos room must NOT trigger an AI reply."""
    mock_add_task = mocker.patch("fastapi.BackgroundTasks.add_task")

    async def override_get_async_session():
        async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with async_session_factory() as session:
            yield session

    def override_auth():
        return user

    app.dependency_overrides[get_async_session] = override_get_async_session
    app.dependency_overrides[get_current_user] = override_auth

    try:
        with TestClient(app) as c:
            resp = c.post(
                "/api/chat/rooms/cooking_videos/messages/",
                json={"text": "動画を確認します"},
            )
        assert resp.status_code == 201
        mock_add_task.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_generate_coaching_reply_with_session_context(
    engine, db, user, dish, chatroom, completed_session, mocker
):
    """_generate_coaching_reply persists an AI message when session context exists."""
    from backend.routers.chat import _generate_coaching_reply

    mock_client = mocker.MagicMock()
    mock_client.models.generate_content.return_value.text = "火力を上げてみましょう！"
    mocker.patch("backend.routers.chat.genai.Client", return_value=mock_client)
    mocker.patch("backend.routers.chat.get_engine", return_value=engine)

    _generate_coaching_reply(
        session_id=completed_session.id,
        user_id=user.id,
        room_id=chatroom.id,
        user_text="チャーハンがうまくできません",
    )

    ai_messages = db.exec(
        select(Message).where(
            Message.chat_room_id == chatroom.id,
            Message.sender == "ai",
        )
    ).all()
    assert len(ai_messages) == 1
    assert "火力を上げてみましょう" in ai_messages[0].text


def test_generate_coaching_reply_fallback_no_session(engine, db, user, chatroom, mocker):
    """_generate_coaching_reply uses a fallback message when no completed session."""
    from backend.routers.chat import _generate_coaching_reply

    mocker.patch("backend.routers.chat.get_engine", return_value=engine)

    _generate_coaching_reply(
        session_id=None,
        user_id=user.id,
        room_id=chatroom.id,
        user_text="料理について教えてください",
    )

    ai_messages = db.exec(
        select(Message).where(
            Message.chat_room_id == chatroom.id,
            Message.sender == "ai",
        )
    ).all()
    assert len(ai_messages) == 1
    # Fallback response should prompt user to complete a session
    assert ai_messages[0].text  # non-empty
