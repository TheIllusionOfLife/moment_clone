import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from google import genai
from google.genai import types
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, col, select

from backend.core.auth import get_current_user
from backend.core.database import get_async_session, get_engine
from backend.core.settings import settings
from backend.models.chat import ChatRoom, Message
from backend.models.dish import Dish
from backend.models.learner_state import LearnerState
from backend.models.session import CookingSession
from backend.models.user import User
from backend.services.gcs import generate_signed_url

router = APIRouter(prefix="/api/chat", tags=["chat"])

VALID_ROOM_TYPES = {"coaching", "cooking_videos"}


# ---------------------------------------------------------------------------
# Reusable ownership dependency
# ---------------------------------------------------------------------------


async def get_owned_chatroom(
    room_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> ChatRoom:
    if room_type not in VALID_ROOM_TYPES:
        raise HTTPException(status_code=404, detail="Chat room not found")
    room = (
        (
            await db.execute(
                select(ChatRoom).where(
                    ChatRoom.user_id == current_user.id,
                    ChatRoom.room_type == room_type,
                )
            )
        )
        .scalars()
        .first()
    )
    if room is None:
        raise HTTPException(status_code=404, detail="Chat room not found")
    return room


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/rooms/")
async def list_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    rooms = (
        (await db.execute(select(ChatRoom).where(ChatRoom.user_id == current_user.id)))
        .scalars()
        .all()
    )
    return [
        {"id": r.id, "room_type": r.room_type, "created_at": r.created_at.isoformat()}
        for r in rooms
    ]


@router.get("/rooms/{room_type}/messages/")
async def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    room: ChatRoom = Depends(get_owned_chatroom),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    offset = (page - 1) * page_size
    messages = (
        (
            await db.execute(
                select(Message)
                .where(Message.chat_room_id == room.id)
                .order_by(col(Message.created_at).desc())
                .offset(offset)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    results = []
    tasks = []
    task_indices = []

    for i, m in enumerate(reversed(messages)):  # return chronological order
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
            tasks.append(
                generate_signed_url(
                    bucket=settings.GCS_BUCKET,
                    object_path=m.video_gcs_path,
                    expiry_days=settings.GCS_SIGNED_URL_EXPIRY_DAYS,
                )
            )
            task_indices.append(i)
        results.append(msg_dict)

    if tasks:
        urls = await asyncio.gather(*tasks)
        for i, url in zip(task_indices, urls):
            results[i]["video_url"] = url

    return {"page": page, "page_size": page_size, "messages": results}


class SendMessageRequest(BaseModel):
    text: str


@router.post("/rooms/{room_type}/messages/", status_code=status.HTTP_201_CREATED)
async def send_message(
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    room: ChatRoom = Depends(get_owned_chatroom),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Message text cannot be empty")

    message = Message(
        chat_room_id=room.id,
        sender="user",
        text=body.text.strip(),
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    if room.room_type == "coaching":
        # Find most recent completed session for context (may be None)
        latest_session = (
            (
                await db.execute(
                    select(CookingSession)
                    .where(
                        CookingSession.user_id == current_user.id,
                        CookingSession.status == "completed",
                    )
                    .order_by(col(CookingSession.created_at).desc())
                )
            )
            .scalars()
            .first()
        )
        session_id = latest_session.id if latest_session else None
        if current_user.id is None or room.id is None:
            raise HTTPException(status_code=500, detail="Invalid user or room state")
        background_tasks.add_task(
            _generate_coaching_reply,
            session_id=session_id,
            user_id=current_user.id,
            room_id=room.id,
            user_text=body.text.strip(),
        )

    return {
        "id": message.id,
        "sender": message.sender,
        "text": message.text,
        "metadata": message.msg_metadata or {},
        "created_at": message.created_at.isoformat(),
    }


def _generate_coaching_reply(
    session_id: int | None,
    user_id: int,
    room_id: int,
    user_text: str,
) -> None:
    """Generate and persist an AI coaching reply in the background.

    Loads session context (coaching_text, video_analysis, dish principles,
    learner state) and calls Gemini with a coaching persona prompt.
    Falls back to a general coaching message when no completed session exists.
    """
    with Session(get_engine()) as db:
        # Load last 10 messages for conversation history
        history = db.exec(
            select(Message)
            .where(Message.chat_room_id == room_id)
            .order_by(col(Message.created_at).desc())
            .limit(10)
        ).all()
        # Reverse to chronological order; drop the most recent user message since
        # it is passed as `contents=user_text` to Gemini — including it in history
        # would duplicate it in the prompt context.
        history_messages = list(reversed(history))
        if history_messages and history_messages[-1].sender == "user":
            history_messages = history_messages[:-1]
        history_text = "\n".join(
            f"{'ユーザー' if m.sender == 'user' else 'コーチ'}: {m.text}"
            for m in history_messages
            if m.text
        )

        # Build context from most recent completed session
        context_parts: list[str] = []
        if session_id is not None:
            session = db.get(CookingSession, session_id)
            if session:
                if session.coaching_text:
                    ct = session.coaching_text
                    context_parts.append(
                        f"前回のフィードバック: 課題={ct.get('mondaiten', '')}, "
                        f"スキル={ct.get('skill', '')}"
                    )
                if session.video_analysis:
                    context_parts.append(f"動画診断: {session.video_analysis.get('diagnosis', '')}")
                dish = db.get(Dish, session.dish_id)
                if dish and dish.principles:
                    context_parts.append(f"料理の原則: {', '.join(dish.principles)}")

        learner_state = db.exec(select(LearnerState).where(LearnerState.user_id == user_id)).first()
        if learner_state and learner_state.skills_developing:
            context_parts.append(f"習得中のスキル: {', '.join(learner_state.skills_developing)}")

        if not context_parts:
            # No completed session — use fallback message
            reply = (
                "まだコーチングセッションが完了していません。"
                "まず料理動画をアップロードして、AIコーチからのフィードバックを受け取ってみましょう！"
                "動画を撮影・アップロードすると、約2〜3分で詳しいフィードバックをお届けします。"
            )
        else:
            context_str = "\n".join(context_parts)
            # Use system_instruction to isolate user content from AI persona prompt,
            # preventing prompt injection via crafted user messages.
            system_instruction = (
                "あなたは料理コーチです。ユーザーの料理スキル向上を支援します。"
                "以下のコンテキストを参考に、具体的で実践的なアドバイスを日本語で提供してください。\n\n"
                f"コンテキスト:\n{context_str}\n\n"
                f"会話履歴:\n{history_text}"
            )
            gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            try:
                response = gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=user_text,
                    config=types.GenerateContentConfig(system_instruction=system_instruction),
                )
                reply = response.text or ""
            except Exception:
                reply = "申し訳ありません。一時的なエラーが発生しました。しばらくしてからもう一度お試しください。"

        ai_message = Message(
            chat_room_id=room_id,
            sender="ai",
            session_id=session_id,
            text=reply,
        )
        db.add(ai_message)
        db.commit()
