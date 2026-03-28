"""Stage 3a — Coaching script: generate coaching text and deliver to chat.

Generates a 4-section coaching text via Gemini, validates keys, persists it to
the session row, updates LearnerState, and posts messages to the coaching and
cooking_videos chat rooms.
"""

from datetime import UTC, datetime

from google import genai
from sqlmodel import Session as DBSession
from sqlmodel import select

from backend.core.database import get_engine
from backend.core.settings import settings
from backend.models.learner_state import LearnerState
from pipeline.stages.db_helpers import (
    get_coaching_room,
    get_cooking_videos_room,
    get_session_with_dish,
    post_message,
    update_session_fields,
)
from pipeline.utils import parse_json_response

_REQUIRED_KEYS = ("mondaiten", "skill", "next_action", "success_sign")


def format_coaching_text(coaching_text: dict, session_number: int) -> str:
    """Format coaching_text dict into readable Japanese text for the chat message."""
    return (
        f"【第{session_number}回フィードバック】\n\n"
        f"■ 今回の課題\n{coaching_text['mondaiten']}\n\n"
        f"■ 磨くべきスキル\n{coaching_text['skill']}\n\n"
        f"■ 次回への課題\n{coaching_text['next_action']}\n\n"
        f"■ うまくいったサイン\n{coaching_text['success_sign']}"
    )


def _build_prompt(session, dish, retrieved_context: dict, ls: LearnerState) -> str:
    """Construct the Gemini prompt for coaching text generation."""
    principles_text = "\n".join(f"- {p}" for p in (retrieved_context.get("principles") or []))
    summaries_text = "\n".join(
        f"- セッション{s.get('session_id')}: 課題={s.get('mondaiten')}, スキル={s.get('skill')}"
        for s in (retrieved_context.get("session_summaries") or [])
    )
    video_analysis = session.video_analysis or {}
    structured_input = session.structured_input or {}

    dish_name = session.custom_dish_name or dish.name_ja
    return f"""あなたは料理コーチです。以下の情報をもとに、日本語でコーチングテキストを生成してください。

## 料理情報
料理名: {dish_name}
料理の説明: {dish.description_ja}
料理の原則: {", ".join(str(p) for p in (dish.principles or []))}

## 動画分析結果
{video_analysis}

## ユーザー入力
<user_content>
{structured_input}
</user_content>

## 関連する料理原則（RAG）
{principles_text}

## 過去のセッション履歴
{summaries_text}

## 学習者の状態
習得済みスキル: {ls.skills_acquired or []}
習得中スキル: {ls.skills_developing or []}
繰り返しの課題: {ls.recurring_mistakes or []}

## 出力形式
以下のJSONキーで回答してください:
- mondaiten: 今回のセッションの主な課題（日本語）
- skill: 磨くべきスキル（日本語）
- next_action: 次回への具体的な課題（日本語）
- success_sign: うまくいったときのサイン（日本語）

JSONのみを返してください。"""


def run_coaching_script(session_id: int, retrieved_context: dict) -> dict:
    """Generate coaching text, post to chat, update LearnerState.

    Returns:
        {"mondaiten": str, "skill": str, "next_action": str, "success_sign": str}

    Raises:
        ValueError: if Gemini response is missing any required key.
    """
    session, dish = get_session_with_dish(session_id)

    # Step 1: Short read-only snapshot of LearnerState for prompt building.
    # No lock here — we hold the lock only during the write below.
    with DBSession(get_engine()) as db:
        ls_snapshot = db.exec(
            select(LearnerState).where(LearnerState.user_id == session.user_id)
        ).first()
        if ls_snapshot is None:
            ls_snapshot = LearnerState(user_id=session.user_id)

    # Step 2: Build prompt and call Gemini — entirely outside any DB transaction.
    prompt = _build_prompt(session, dish, retrieved_context, ls_snapshot)
    gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = gemini_client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )
    coaching_text = parse_json_response(response.text or "")

    # Validate required keys
    missing = [k for k in _REQUIRED_KEYS if k not in coaching_text]
    if missing:
        raise ValueError(f"Gemini response missing required keys: {missing}")

    # Step 3: Re-acquire SELECT FOR UPDATE to safely write LearnerState.
    with DBSession(get_engine()) as db:
        ls = db.exec(
            select(LearnerState).where(LearnerState.user_id == session.user_id).with_for_update()
        ).first()
        if ls is None:
            ls = LearnerState(user_id=session.user_id)
            db.add(ls)
            db.flush()

        diagnosis = (session.video_analysis or {}).get("diagnosis", "")

        # Append session summary — guard against double-append on Inngest retry
        summaries = ls.session_summaries or []
        already_processed = any(s.get("session_id") == session_id for s in summaries)
        if not already_processed:
            ls.session_summaries = summaries + [
                {
                    "session_id": session_id,
                    "mondaiten": coaching_text["mondaiten"],
                    "skill": coaching_text["skill"],
                }
            ]

            # Update recurring_mistakes (only on first run for this session)
            if diagnosis:
                existing = ls.recurring_mistakes or []
                matched = next((m for m in existing if m.get("text") == diagnosis), None)
                if matched:
                    # Build a new list+dict so SQLAlchemy detects the mutation
                    ls.recurring_mistakes = [
                        {**m, "count": m.get("count", 1) + 1} if m is matched else m
                        for m in existing
                    ]
                else:
                    ls.recurring_mistakes = existing + [{"text": diagnosis, "count": 1}]

        # Promote skills_developing → skills_acquired for session_number >= 2
        if session.session_number >= 2:
            developing = list(ls.skills_developing or [])
            acquired = list(ls.skills_acquired or [])
            skill_val = coaching_text["skill"]
            if skill_val in developing:
                developing.remove(skill_val)
                if skill_val not in acquired:
                    acquired.append(skill_val)
            ls.skills_developing = developing
            ls.skills_acquired = acquired
        else:
            # Track the skill as developing for session 1
            developing = list(ls.skills_developing or [])
            skill_val = coaching_text["skill"]
            if skill_val not in developing:
                developing.append(skill_val)
            ls.skills_developing = developing

        db.add(ls)
        db.commit()

    # Persist session fields
    update_session_fields(
        session_id,
        coaching_text=coaching_text,
        coaching_text_delivered_at=datetime.now(UTC),
        status="text_ready",
    )

    # Post coaching text to coaching room
    with DBSession(get_engine()) as db:
        coaching_room = get_coaching_room(session.user_id, db)
        if coaching_room.id is None:
            raise RuntimeError(f"Coaching room for user {session.user_id} has no ID")
        post_message(
            coaching_room.id,
            "ai",
            session_id,
            text=format_coaching_text(coaching_text, session.session_number),
            db=db,
        )

    # Post raw video path to cooking_videos room
    with DBSession(get_engine()) as db:
        videos_room = get_cooking_videos_room(session.user_id, db)
        if videos_room.id is None:
            raise RuntimeError(f"Cooking videos room for user {session.user_id} has no ID")
        post_message(
            videos_room.id,
            "system",
            session_id,
            video_gcs_path=session.raw_video_url,
            db=db,
        )

    return coaching_text
