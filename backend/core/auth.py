import asyncio
import time
from typing import Annotated

import httpx
import jwt
from cachetools import TTLCache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.core.database import get_async_session
from backend.core.settings import settings
from backend.models.user import User

_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)
_cache_lock = asyncio.Lock()
_bearer = HTTPBearer()
# Tracks when we last force-refreshed JWKS; guards against DoS via unknown-kid tokens.
_last_force_refresh_at: float = float("-inf")
_FORCE_REFRESH_INTERVAL = 60.0  # seconds


async def _fetch_jwks(force_refresh: bool = False) -> dict:
    # Fast path: atomic read via .get() avoids KeyError if TTL evicts between check and access
    if not force_refresh:
        cached = _jwks_cache.get("jwks")
        if cached is not None:
            return cached
    async with _cache_lock:
        # Re-check inside lock to handle concurrent waiters
        if not force_refresh:
            cached = _jwks_cache.get("jwks")
            if cached is not None:
                return cached
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(settings.CLERK_JWKS_URL, timeout=10)
            resp.raise_for_status()
        except httpx.HTTPError as err:
            stale = _jwks_cache.get("jwks")
            if stale is not None:
                return stale
            raise HTTPException(
                status_code=503,
                detail="Failed to fetch JWKS from Clerk",
            ) from err
        data = resp.json()
        _jwks_cache["jwks"] = data
        return data


async def _public_key_for_kid(kid: str, force_refresh: bool = False):
    global _last_force_refresh_at

    jwks = await _fetch_jwks(force_refresh=force_refresh)
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)

    if not force_refresh:
        # Retry once with a fresh JWKS in case Clerk recently rotated keys.
        # Rate-limited to _FORCE_REFRESH_INTERVAL to prevent DoS via unknown-kid tokens.
        async with _cache_lock:
            now = time.monotonic()
            if now - _last_force_refresh_at >= _FORCE_REFRESH_INTERVAL:
                _last_force_refresh_at = now
                do_refresh = True
            else:
                do_refresh = False
        if do_refresh:
            return await _public_key_for_kid(kid, force_refresh=True)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unknown signing key",
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: AsyncSession = Depends(get_async_session),
) -> User:
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        ) from err

    public_key = await _public_key_for_kid(header.get("kid", ""))

    # Verify audience/issuer only when explicitly configured.
    # Clerk JWTs omit the aud claim by default; iss is the Clerk frontend API URL.
    verify_aud = bool(settings.CLERK_AUDIENCE)
    decode_kwargs: dict = {
        "algorithms": ["RS256"],
        "options": {"verify_aud": verify_aud},
    }
    if verify_aud:
        decode_kwargs["audience"] = settings.CLERK_AUDIENCE
    if settings.CLERK_ISSUER:
        decode_kwargs["issuer"] = settings.CLERK_ISSUER

    try:
        payload = jwt.decode(token, public_key, **decode_kwargs)
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

    user = (
        (await db.execute(select(User).where(User.clerk_user_id == clerk_user_id)))
        .scalars()
        .first()
    )
    if user is None:
        # Return 401 not 404 — avoids user enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
