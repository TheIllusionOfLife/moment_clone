from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "user"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    clerk_user_id: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    first_name: str
    onboarding_done: bool = Field(default=False)
    subscription_status: str = Field(default="free")
    learner_profile: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
