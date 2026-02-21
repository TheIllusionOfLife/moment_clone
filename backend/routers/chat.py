from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from backend.core.auth import get_current_user
from backend.core.database import get_session
from backend.core.settings import settings
from backend.models.chat import ChatRoom, Message
from backend.models.user import User
from backend.services.gcs import generate_signed_url

router = APIRouter(prefix="/api/chat", tags=["chat"])

VALID_ROOM_TYPES = {"coaching", "cooking_videos"}


# ---------------------------------------------------------------------------
# Reusable ownership dependency
# ---------------------------------------------------------------------------


def get_owned_chatroom(
    room_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatRoom:
    if room_type not in VALID_ROOM_TYPES:
        raise HTTPException(status_code=404, detail="Chat room not found")
    room = db.exec(
        select(ChatRoom).where(
            ChatRoom.user_id == current_user.id,
            ChatRoom.room_type == room_type,
        )
    ).first()
    if room is None:
        raise HTTPException(status_code=404, detail="Chat room not found")
    return room


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/rooms/")
def list_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[dict]:
    rooms = db.exec(select(ChatRoom).where(ChatRoom.user_id == current_user.id)).all()
    return [{"id": r.id, "room_type": r.room_type, "created_at": r.created_at.isoformat()} for r in rooms]


@router.get("/rooms/{room_type}/messages/")
def list_messages(
    room_type: str,
    page: int = 1,
    page_size: int = 50,
    room: ChatRoom = Depends(get_owned_chatroom),
    db: Session = Depends(get_session),
) -> dict:
    offset = (page - 1) * page_size
    messages = db.exec(
        select(Message)
        .where(Message.chat_room_id == room.id)
        .order_by(col(Message.created_at).desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    results = []
    for m in reversed(messages):  # return chronological order
        msg_dict: dict = {
            "id": m.id,
            "sender": m.sender,
            "text": m.text,
            "video_url": None,
            "metadata": m.msg_metadata or {},
            "session_id": m.session_id,
            "created_at": m.created_at.isoformat(),
        }
        if m.video_gcs_path:
            msg_dict["video_url"] = generate_signed_url(
                bucket=settings.GCS_BUCKET,
                object_path=m.video_gcs_path,
                expiry_days=settings.GCS_SIGNED_URL_EXPIRY_DAYS,
            )
        results.append(msg_dict)

    return {"page": page, "page_size": page_size, "messages": results}


class SendMessageRequest(BaseModel):
    text: str


@router.post("/rooms/{room_type}/messages/", status_code=status.HTTP_201_CREATED)
def send_message(
    body: SendMessageRequest,
    room: ChatRoom = Depends(get_owned_chatroom),
    db: Session = Depends(get_session),
) -> dict:
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Message text cannot be empty")

    message = Message(
        chat_room_id=room.id,
        sender="user",
        text=body.text.strip(),
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    # AI Q&A response is handled asynchronously in Phase 2 (coaching pipeline)
    return {
        "id": message.id,
        "sender": message.sender,
        "text": message.text,
        "metadata": message.msg_metadata or {},
        "created_at": message.created_at.isoformat(),
    }
