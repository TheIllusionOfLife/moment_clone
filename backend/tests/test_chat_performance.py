import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from backend.models.chat import ChatRoom, Message
from backend.core.auth import get_current_user
from backend.core.database import get_async_session
from sqlalchemy.ext.asyncio import async_sessionmaker

@pytest.mark.asyncio
async def test_list_messages_performance(app, async_engine, user, mocker):
    # Setup
    # Create a chat room
    async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with async_session_factory() as db:
        room = ChatRoom(user_id=user.id, room_type="coaching")
        db.add(room)
        await db.commit()
        await db.refresh(room)
        room_id = room.id

        # Create 20 messages with video_gcs_path
        messages = []
        for i in range(20):
            msg = Message(
                chat_room_id=room_id,
                sender="user",
                text=f"msg {i}",
                video_gcs_path=f"videos/{i}.mp4"
            )
            db.add(msg)
        await db.commit()

    # Mock generate_signed_url with a delay
    async def mock_generate_signed_url(*args, **kwargs):
        await asyncio.sleep(0.05) # 50ms delay
        return "http://signed.url"

    mocker.patch("backend.routers.chat.generate_signed_url", side_effect=mock_generate_signed_url)

    # Setup client override
    def override_auth():
        return user

    async def override_get_async_session():
         async with async_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_auth
    app.dependency_overrides[get_async_session] = override_get_async_session

    client = TestClient(app)

    # Measure time
    start_time = time.time()
    response = client.get("/api/chat/rooms/coaching/messages/?page_size=50")
    end_time = time.time()

    duration = end_time - start_time

    print(f"\nDuration: {duration:.4f}s")

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 20

    # We assert strict upper bound for parallel execution.
    # If sequential: 20 * 0.05 = 1.0s.
    # If parallel: ~0.05s + overhead.
    # So 0.5s is a very safe upper bound for parallel.
    assert duration < 0.5, f"Too slow! Took {duration:.4f}s"
