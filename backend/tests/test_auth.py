"""Tests for JWT auth middleware."""

from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.core.auth import get_current_user


def test_missing_auth_header(app):
    with TestClient(app) as client:
        resp = client.get("/api/auth/me/")
    assert resp.status_code == 401


def test_invalid_token_format(app):
    with TestClient(app) as client:
        resp = client.get("/api/auth/me/", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


@pytest.fixture()
def private_key():
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def test_unknown_kid_returns_401(app, user, private_key):
    """Token with a kid not in JWKS -> 401."""
    token = jwt.encode(
        {"sub": user.clerk_user_id, "kid": "unknown-kid"},
        private_key,
        algorithm="RS256",
        headers={"kid": "unknown-kid"},
    )

    with patch("backend.core.auth._fetch_jwks", return_value={"keys": []}):
        with TestClient(app) as client:
            resp = client.get("/api/auth/me/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_valid_token_returns_user(app, user, private_key):
    """Valid RS256 token -> GET /api/auth/me/ returns user JSON.

    We override get_current_user to avoid needing a live JWKS endpoint.
    """
    token = jwt.encode({"sub": user.clerk_user_id}, private_key, algorithm="RS256")

    # Override get_current_user to return the user directly (avoids JWKS complexity)
    def override_auth():
        return user

    app.dependency_overrides[get_current_user] = override_auth

    with TestClient(app) as client:
        resp = client.get("/api/auth/me/", headers={"Authorization": f"Bearer {token}"})

    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    data = resp.json()
    assert data["clerk_user_id"] == user.clerk_user_id


def test_patch_me_updates_profile(app, user, db):
    """PATCH /api/auth/me/ persists learner_profile and sets onboarding_done."""
    from backend.core.auth import get_current_user

    # Detach from the sync session so the async session in the endpoint can adopt it
    db.expunge(user)
    app.dependency_overrides[get_current_user] = lambda: user

    payload = {"learner_profile": {"skill_level": "beginner", "goal": "daily"}}
    with TestClient(app) as client:
        resp = client.patch("/api/auth/me/", json=payload)

    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    data = resp.json()
    assert data["onboarding_done"] is True
    assert data["learner_profile"] == payload["learner_profile"]


def test_patch_me_unauthenticated(app):
    """PATCH /api/auth/me/ without auth header returns 401/403."""
    with TestClient(app) as client:
        resp = client.patch("/api/auth/me/", json={"learner_profile": {}})
    assert resp.status_code in (401, 403)


def test_patch_me_invalid_payload(app, user):
    """PATCH /api/auth/me/ with missing learner_profile returns 422."""
    from backend.core.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as client:
        resp = client.patch("/api/auth/me/", json={"wrong_field": "value"})

    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 422


def test_jwks_force_refresh_rate_limited(app, private_key):
    """Multiple unknown-kid requests within the interval trigger only one JWKS force-refresh."""
    import backend.core.auth as auth_module

    token = jwt.encode(
        {"sub": "any"},
        private_key,
        algorithm="RS256",
        headers={"kid": "unknown-kid"},
    )

    force_refresh_calls = [0]

    async def counting_fetch(force_refresh: bool = False) -> dict:
        if force_refresh:
            force_refresh_calls[0] += 1
        # Return empty JWKS — no keys match "unknown-kid", triggering the retry path.
        # Do NOT call original_fetch to avoid a real HTTP request in tests.
        return {"keys": []}

    # Reset rate-limit state so the first request is always allowed to refresh.
    original_ts = auth_module._last_force_refresh_at
    auth_module._last_force_refresh_at = float("-inf")

    try:
        with patch("backend.core.auth._fetch_jwks", side_effect=counting_fetch):
            for _ in range(3):
                with TestClient(app) as client:
                    client.get("/api/auth/me/", headers={"Authorization": f"Bearer {token}"})
    finally:
        auth_module._last_force_refresh_at = original_ts

    # All three requests carry an unknown kid, but only the first triggers a force-refresh.
    assert force_refresh_calls[0] == 1
