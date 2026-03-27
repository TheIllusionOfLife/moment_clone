from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.models.user_dish_progress import UserDishProgress


def test_list_dishes_unauthenticated(app):
    """GET /api/dishes/ without auth header returns 401."""
    with TestClient(app) as client:
        resp = client.get("/api/dishes/")
    assert resp.status_code == 401


def test_list_dishes_returns_list(app, user, dish):
    """GET /api/dishes/ returns a list of dishes."""
    # Override authentication
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as client:
        resp = client.get("/api/dishes/")

    # Cleanup override
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    target_dish = next((d for d in data if d["id"] == dish.id), None)
    assert target_dish is not None
    assert target_dish["slug"] == dish.slug
    assert target_dish["progress"]["status"] == "not_started"


def test_list_dishes_includes_progress(app, user, dish, db):
    """GET /api/dishes/ includes progress for the user."""
    # Create progress
    progress = UserDishProgress(
        user_id=user.id,
        dish_id=dish.id,
        status="in_progress",
        started_at=datetime.now(UTC),
    )
    db.add(progress)
    db.commit()
    db.refresh(progress)

    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as client:
        resp = client.get("/api/dishes/")

    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    data = resp.json()

    target_dish = next((d for d in data if d["id"] == dish.id), None)
    assert target_dish is not None
    assert target_dish["progress"]["status"] == "in_progress"
    assert target_dish["progress"]["started_at"] is not None


def test_get_dish_returns_dish(app, user, dish):
    """GET /api/dishes/{slug}/ returns the dish."""
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as client:
        resp = client.get(f"/api/dishes/{dish.slug}/")

    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == dish.id
    assert data["slug"] == dish.slug


def test_get_dish_404(app, user):
    """GET /api/dishes/{slug}/ returns 404 for non-existent dish."""
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as client:
        resp = client.get("/api/dishes/non-existent-slug/")

    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 404
