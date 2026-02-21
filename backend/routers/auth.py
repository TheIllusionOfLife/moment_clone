import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlmodel import Session, select
from svix.webhooks import Webhook, WebhookVerificationError

from backend.core.auth import get_current_user
from backend.core.database import get_session
from backend.core.settings import settings
from backend.models.chat import ChatRoom
from backend.models.learner_state import LearnerState
from backend.models.user import User

router = APIRouter()

# In-memory idempotency set for webhook deduplication.
# For multi-instance deployments, replace with a Redis SET with TTL.
_processed_webhook_ids: set[str] = set()


@router.post("/api/webhooks/clerk/", status_code=200)
async def clerk_webhook(
    request: Request,
    db: Session = Depends(get_session),
    svix_id: str = Header(alias="svix-id"),
    svix_timestamp: str = Header(alias="svix-timestamp"),
    svix_signature: str = Header(alias="svix-signature"),
) -> dict:
    # Idempotency: skip already-processed events
    if svix_id in _processed_webhook_ids:
        return {"status": "already_processed"}

    body = await request.body()

    # Verify signature via svix library (handles timestamp tolerance ±5 min)
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
            (e["email_address"] for e in email_addresses if e["id"] == primary_email_id),
            email_addresses[0]["email_address"] if email_addresses else "",
        )
        first_name: str = data.get("first_name") or data.get("username") or "User"

        existing = db.exec(select(User).where(User.clerk_user_id == clerk_user_id)).first()
        if existing is None:
            user = User(
                clerk_user_id=clerk_user_id,
                email=email,
                first_name=first_name,
            )
            db.add(user)
            db.flush()  # populate user.id before FK references

            db.add(LearnerState(user_id=user.id))
            db.add(ChatRoom(user_id=user.id, room_type="coaching"))
            db.add(ChatRoom(user_id=user.id, room_type="cooking_videos"))
            db.commit()

    _processed_webhook_ids.add(svix_id)
    return {"status": "ok"}


@router.get("/api/auth/me/")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
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
