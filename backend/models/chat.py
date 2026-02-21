from datetime import UTC, datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class ChatRoom(SQLModel, table=True):
    __tablename__ = "chatroom"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("user_id", "room_type"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    room_type: str  # "coaching" | "cooking_videos"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Message(SQLModel, table=True):
    __tablename__ = "message"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    chat_room_id: int = Field(foreign_key="chatroom.id", index=True)
    sender: str  # "user" | "ai" | "system"
    session_id: int | None = Field(default=None, foreign_key="session.id")

    # Exactly one of text / video_gcs_path is populated per message
    text: str = Field(default="")
    video_gcs_path: str = Field(default="")
    # Field named 'metadata' is reserved by SQLAlchemy; use msg_metadata mapped to the DB column.
    msg_metadata: dict | None = Field(default=None, sa_column=Column("metadata", JSON))

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
