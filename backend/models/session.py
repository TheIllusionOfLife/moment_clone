from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class CookingSession(SQLModel, table=True):
    """One cook of one dish = one session. Max 3 per dish.

    Named CookingSession to avoid collision with sqlmodel.Session.
    Maps to the 'session' table in Supabase.
    """

    __tablename__ = "session"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("user_id", "dish_id", "session_number"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    dish_id: int = Field(foreign_key="dish.id")
    session_number: int  # 1–3 for regular dishes; unlimited for slug='free' (no DB CHECK)

    # For free-choice dish: user-supplied dish name stored with the session
    custom_dish_name: str | None = None

    # User input
    raw_video_url: str = Field(default="")
    voice_memo_url: str | None = None
    self_ratings: dict | None = Field(default=None, sa_column=Column(JSON))
    voice_transcript: str = Field(default="")
    structured_input: dict | None = Field(default=None, sa_column=Column(JSON))

    # Pipeline state
    status: str = Field(default="pending_upload")
    pipeline_job_id: UUID | None = Field(default=None)
    pipeline_started_at: datetime | None = None
    pipeline_error: str = Field(default="")

    # AI analysis output (Stage 1)
    video_analysis: dict | None = Field(default=None, sa_column=Column(JSON))

    # Coaching output (Stage 3a)
    coaching_text: dict | None = Field(default=None, sa_column=Column(JSON))
    coaching_text_delivered_at: datetime | None = None

    # Narration script (Stage 3b)
    narration_script: dict | None = Field(default=None, sa_column=Column(JSON))

    # Video output (Stage 4) — GCS object path; signed URL generated at read time
    coaching_video_gcs_path: str = Field(default="")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
