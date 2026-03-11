
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

def test_list_sessions_returns_empty_heavy_fields(client, db, user, dish):
    from backend.models.session import CookingSession

    # Create a session with heavy data
    heavy_data = {"data": "x" * 100}
    s = CookingSession(
        user_id=user.id,
        dish_id=dish.id,
        session_number=1,
        video_analysis=heavy_data,
        narration_script=heavy_data,
        status="completed"
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    # Call list_sessions
    resp = client.get("/api/sessions/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    session_data = data[0]

    # Assert heavy fields are empty/summary
    # Note: Before optimization, these would be equal to heavy_data
    # After optimization, they should be empty dicts
    assert session_data["video_analysis"] == {}
    assert session_data["narration_script"] == {}

    # Assert other fields are present
    assert session_data["id"] == s.id
    assert session_data["status"] == "completed"

def test_get_session_detail_returns_full_data(client, db, user, dish):
    from backend.models.session import CookingSession

    heavy_data = {"data": "x" * 100}
    s = CookingSession(
        user_id=user.id,
        dish_id=dish.id,
        session_number=2,
        video_analysis=heavy_data,
        narration_script=heavy_data,
        status="completed"
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    # Call get_session_detail
    resp = client.get(f"/api/sessions/{s.id}/")
    assert resp.status_code == 200
    session_data = resp.json()

    # Assert heavy fields are present
    assert session_data["video_analysis"] == heavy_data
    assert session_data["narration_script"] == heavy_data
