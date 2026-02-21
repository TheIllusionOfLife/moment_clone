import threading
from typing import Annotated

import httpx
import jwt
from cachetools import TTLCache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from backend.core.database import get_session
from backend.core.settings import settings
from backend.models.user import User

_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)
_cache_lock = threading.Lock()
_bearer = HTTPBearer()


def _fetch_jwks() -> dict:
    with _cache_lock:
        if "jwks" in _jwks_cache:
            return _jwks_cache["jwks"]
        resp = httpx.get(settings.CLERK_JWKS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        _jwks_cache["jwks"] = data
        return data


def _public_key_for_kid(kid: str):
    jwks = _fetch_jwks()
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unknown signing key",
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Session = Depends(get_session),
) -> User:
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        ) from err

    public_key = _public_key_for_kid(header.get("kid", ""))

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from err
    except jwt.PyJWTError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from err

    clerk_user_id: str = payload.get("sub", "")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing subject claim",
        )

    user = db.exec(select(User).where(User.clerk_user_id == clerk_user_id)).first()
    if user is None:
        # Return 401 not 404 — avoids user enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
