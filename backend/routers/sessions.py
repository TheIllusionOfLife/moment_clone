import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from backend.core.auth import get_current_user
from backend.core.database import get_async_session
from backend.core.settings import settings
from backend.models.dish import Dish
from backend.models.session import CookingSession
from backend.models.user import User
from backend.services.gcs import generate_signed_url, upload_file
from backend.services.inngest_client import send_video_uploaded

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

ALLOWED_VIDEO_MIMES = {"video/mp4", "video/quicktime"}
MAX_VIDEO_BYTES = 500 * 1024 * 1024  # 500 MB

ALLOWED_AUDIO_MIMES = {"audio/mp4", "audio/mpeg", "audio/wav", "audio/webm", "audio/m4a"}
MAX_AUDIO_BYTES = 100 * 1024 * 1024  # 100 MB

_CHUNK_SIZE = 1024 * 1024  # 1 MB read chunks


# ---------------------------------------------------------------------------
# Reusable ownership dependency
# ---------------------------------------------------------------------------


async def get_owned_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> CookingSession:
    cooking_session = await db.get(CookingSession, session_id)
    if not cooking_session or cooking_session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return cooking_session


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    dish_slug: str
    custom_dish_name: str | None = None  # required when dish_slug == "free"


class RatingsRequest(BaseModel):
    appearance: int = Field(ge=1, le=5)
    taste: int = Field(ge=1, le=5)
    texture: int = Field(ge=1, le=5)
    aroma: int = Field(ge=1, le=5)


class MemoTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def list_sessions(
    dish_slug: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    stmt = select(CookingSession).where(CookingSession.user_id == current_user.id)
    if dish_slug:
        dish = (await db.execute(select(Dish).where(Dish.slug == dish_slug))).scalars().first()
        if dish is None:
            raise HTTPException(status_code=404, detail="Dish not found")
        stmt = stmt.where(CookingSession.dish_id == dish.id)
    sessions = (
        (await db.execute(stmt.order_by(col(CookingSession.created_at).desc()))).scalars().all()
    )
    return [await _session_to_dict(s) for s in sessions]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    dish = (await db.execute(select(Dish).where(Dish.slug == body.dish_slug))).scalars().first()
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")

    existing = (
        (
            await db.execute(
                select(CookingSession).where(
                    CookingSession.user_id == current_user.id,
                    CookingSession.dish_id == dish.id,
                )
            )
        )
        .scalars()
        .all()
    )
    session_number = len(existing) + 1
    if dish.slug != "free" and session_number > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 sessions per dish")

    if dish.slug == "free" and not (body.custom_dish_name or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="custom_dish_name is required for free-choice sessions",
        )

    cooking_session = CookingSession(
        user_id=current_user.id,
        dish_id=dish.id,
        session_number=session_number,
        # custom_dish_name is only meaningful for the free-choice dish
        custom_dish_name=body.custom_dish_name or None if dish.slug == "free" else None,
    )
    db.add(cooking_session)
    try:
        await db.commit()
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Session already exists") from err
    await db.refresh(cooking_session)
    return await _session_to_dict(cooking_session)


@router.post("/{session_id}/upload/")
async def upload_video(
    video: UploadFile = File(...),
    owned_session: CookingSession = Depends(get_owned_session),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    if video.content_type not in ALLOWED_VIDEO_MIMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid content type '{video.content_type}'. Allowed: {sorted(ALLOWED_VIDEO_MIMES)}",
        )

    # Stream size check without accumulating bytes in Python memory.
    size = 0
    while chunk := await video.read(_CHUNK_SIZE):
        size += len(chunk)
        if size > MAX_VIDEO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Video exceeds 500 MB limit",
            )

    # Seek back so GCS can read from the start via the underlying SpooledTemporaryFile.
    await video.seek(0)

    object_path = f"sessions/{owned_session.id}/raw_video_{uuid.uuid4().hex}.mp4"
    gcs_path = await upload_file(
        bucket=settings.GCS_BUCKET,
        object_path=object_path,
        file_obj=video.file,
        content_type=video.content_type or "video/mp4",
    )

    owned_session.raw_video_url = gcs_path
    owned_session.status = "uploaded"
    owned_session.pipeline_job_id = uuid.uuid4()
    db.add(owned_session)
    await db.commit()
    await db.refresh(owned_session)

    assert owned_session.id is not None  # always set after db.refresh()
    await send_video_uploaded(owned_session.id, owned_session.user_id)

    return await _session_to_dict(owned_session)


@router.post("/{session_id}/voice-memo/")
async def upload_voice_memo(
    audio: UploadFile = File(...),
    owned_session: CookingSession = Depends(get_owned_session),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    if audio.content_type not in ALLOWED_AUDIO_MIMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid audio type '{audio.content_type}'. Allowed: {sorted(ALLOWED_AUDIO_MIMES)}",
        )

    size = 0
    while chunk := await audio.read(_CHUNK_SIZE):
        size += len(chunk)
        if size > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Audio exceeds 100 MB limit",
            )

    await audio.seek(0)

    object_path = f"sessions/{owned_session.id}/voice_memo_{uuid.uuid4().hex}"
    gcs_path = await upload_file(
        bucket=settings.GCS_BUCKET,
        object_path=object_path,
        file_obj=audio.file,
        content_type=audio.content_type or "audio/m4a",
    )

    owned_session.voice_memo_url = gcs_path
    db.add(owned_session)
    await db.commit()
    await db.refresh(owned_session)
    return await _session_to_dict(owned_session)


@router.patch("/{session_id}/ratings/")
async def save_ratings(
    body: RatingsRequest,
    owned_session: CookingSession = Depends(get_owned_session),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    owned_session.self_ratings = body.model_dump()
    owned_session.updated_at = datetime.now(UTC)
    db.add(owned_session)
    await db.commit()
    await db.refresh(owned_session)
    return await _session_to_dict(owned_session)


@router.post("/{session_id}/memo-text/")
async def save_memo_text(
    body: MemoTextRequest,
    owned_session: CookingSession = Depends(get_owned_session),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    """Accept a typed self-assessment text instead of a voice memo file.

    Clears voice_memo_url so the pipeline text path always takes precedence —
    both fields cannot coexist on a session.
    """
    owned_session.voice_transcript = body.text.strip()
    owned_session.voice_memo_url = None
    owned_session.updated_at = datetime.now(UTC)
    db.add(owned_session)
    await db.commit()
    await db.refresh(owned_session)
    return await _session_to_dict(owned_session)


@router.get("/{session_id}/")
async def get_session_detail(
    owned_session: CookingSession = Depends(get_owned_session),
) -> dict:
    return await _session_to_dict(owned_session)


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


async def _session_to_dict(s: CookingSession) -> dict:
    raw_video_url = None
    if s.raw_video_url:
        raw_video_url = await generate_signed_url(
            bucket=settings.GCS_BUCKET,
            object_path=s.raw_video_url,
            expiry_days=settings.GCS_SIGNED_URL_EXPIRY_DAYS,
        )
    coaching_video_url = None
    if s.coaching_video_gcs_path:
        coaching_video_url = await generate_signed_url(
            bucket=settings.GCS_BUCKET,
            object_path=s.coaching_video_gcs_path,
            expiry_days=settings.GCS_SIGNED_URL_EXPIRY_DAYS,
        )
    return {
        "id": s.id,
        "user_id": s.user_id,
        "dish_id": s.dish_id,
        "session_number": s.session_number,
        "custom_dish_name": s.custom_dish_name,
        "status": s.status,
        "raw_video_url": raw_video_url,
        "voice_memo_url": s.voice_memo_url,
        "self_ratings": s.self_ratings or {},
        "voice_transcript": s.voice_transcript,
        "structured_input": s.structured_input or {},
        "video_analysis": s.video_analysis or {},
        "coaching_text": s.coaching_text or {},
        "coaching_text_delivered_at": (
            s.coaching_text_delivered_at.isoformat() if s.coaching_text_delivered_at else None
        ),
        "narration_script": s.narration_script or {},
        "coaching_video_url": coaching_video_url,
        "pipeline_error": s.pipeline_error,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }
