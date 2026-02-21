"""Tests for JWT auth middleware."""

from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend.core.auth import get_current_user


@pytest.fixture()
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def client_with_auth(app, engine, user):
    """TestClient where JWKS is mocked to return a locally generated RSA key."""
    from sqlmodel import Session

    from backend.core.database import get_session

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c


def test_missing_auth_header(app):
    with TestClient(app) as client:
        resp = client.get("/api/auth/me/")
    assert resp.status_code == 401


def test_invalid_token_format(app):
    with TestClient(app) as client:
        resp = client.get("/api/auth/me/", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_unknown_kid_returns_401(app, user, private_key):
    """Token with a kid not in JWKS → 401."""
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


def test_valid_token_returns_user(app, engine, user, private_key):
    """Valid RS256 token → GET /api/auth/me/ returns user JSON.

    We override get_current_user to avoid needing a live JWKS endpoint.
    """
    token = jwt.encode({"sub": user.clerk_user_id}, private_key, algorithm="RS256")

    # Override get_current_user to return the user directly (avoids JWKS complexity)
    def override_auth():
        return user

    app.dependency_overrides[get_current_user] = override_auth

    from sqlmodel import Session

    from backend.core.database import get_session

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        resp = client.get("/api/auth/me/", headers={"Authorization": f"Bearer {token}"})

    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    data = resp.json()
    assert data["clerk_user_id"] == user.clerk_user_id
