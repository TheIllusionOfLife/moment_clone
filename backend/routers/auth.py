import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from svix.webhooks import Webhook, WebhookVerificationError

from backend.core.auth import get_current_user
from backend.core.database import get_async_session
from backend.core.settings import settings
from backend.models.chat import ChatRoom
from backend.models.learner_state import LearnerState
from backend.models.user import User
from backend.models.webhook_event import WebhookEvent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/webhooks/clerk/", status_code=200)
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    svix_id: str = Header(alias="svix-id"),
    svix_timestamp: str = Header(alias="svix-timestamp"),
    svix_signature: str = Header(alias="svix-signature"),
) -> dict:
    body = await request.body()

    # Verify signature first — idempotency check must come after to prevent
    # forged svix-id headers from poisoning the deduplication cache.
    wh = Webhook(settings.CLERK_WEBHOOK_SECRET)
    try:
        wh.verify(
            body,
            {
                "svix-id": svix_id,
                "svix-timestamp": svix_timestamp,
                "svix-signature": svix_signature,
            },
        )
    except WebhookVerificationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        ) from err

    # Idempotency: lock the event ID in the DB.
    # If the ID already exists, this is a duplicate delivery -> skip.
    try:
        db.add(WebhookEvent(id=svix_id))
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return {"status": "already_processed"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        ) from err

    event_type = payload.get("type")

    if event_type == "user.created":
        data = payload.get("data", {})
        clerk_user_id: str = data.get("id", "")
        email_addresses: list = data.get("email_addresses", [])
        primary_email_id: str = data.get("primary_email_address_id", "")

        email = next(
            (
                e.get("email_address", "")
                for e in email_addresses
                if e.get("id") == primary_email_id
            ),
            email_addresses[0].get("email_address", "") if email_addresses else "",
        )
        first_name: str = data.get("first_name") or data.get("username") or "User"

        if not clerk_user_id or not email:
            logger.warning(
                "user.created webhook missing clerk_user_id or email; skipping. "
                "clerk_user_id=%r email=%r",
                clerk_user_id,
                email,
            )
            await db.commit()
            return {"status": "ok"}

        existing = (
            (await db.execute(select(User).where(User.clerk_user_id == clerk_user_id)))
            .scalars()
            .first()
        )
        if existing is None:
            # Use a savepoint so if user creation fails (e.g. race condition),
            # we don't lose the WebhookEvent insert which happened earlier.
            try:
                async with db.begin_nested():
                    user = User(
                        clerk_user_id=clerk_user_id,
                        email=email,
                        first_name=first_name,
                    )
                    db.add(user)
                    await db.flush()  # populate user.id before FK references

                    db.add(LearnerState(user_id=user.id))
                    db.add(ChatRoom(user_id=user.id, room_type="coaching"))
                    db.add(ChatRoom(user_id=user.id, room_type="cooking_videos"))
            except IntegrityError:
                # The savepoint rolled back, but the WebhookEvent insert is still valid in the session.
                # Confirm the collision is the expected clerk_user_id duplicate.
                recovered = (
                    (await db.execute(select(User).where(User.clerk_user_id == clerk_user_id)))
                    .scalars()
                    .first()
                )
                if recovered is None:
                    raise
                logger.info(
                    "user.created race: user already exists for clerk_user_id=%r",
                    clerk_user_id,
                )

    await db.commit()
    return {"status": "ok"}


class UpdateMeRequest(BaseModel):
    learner_profile: dict


@router.patch("/api/auth/me/")
async def update_me(
    body: UpdateMeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    current_user.learner_profile = body.learner_profile
    current_user.onboarding_done = True
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return {
        "id": current_user.id,
        "clerk_user_id": current_user.clerk_user_id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "onboarding_done": current_user.onboarding_done,
        "subscription_status": current_user.subscription_status,
        "learner_profile": current_user.learner_profile,
        "created_at": current_user.created_at.isoformat(),
    }


@router.get("/api/auth/me/")
async def get_me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "clerk_user_id": current_user.clerk_user_id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "onboarding_done": current_user.onboarding_done,
        "subscription_status": current_user.subscription_status,
        "learner_profile": current_user.learner_profile,
        "created_at": current_user.created_at.isoformat(),
    }
