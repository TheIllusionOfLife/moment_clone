from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class LearnerState(SQLModel, table=True):
    __tablename__ = "learnerstate"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)

    skills_acquired: list | None = Field(default=None, sa_column=Column(JSON))
    skills_developing: list | None = Field(default=None, sa_column=Column(JSON))
    recurring_mistakes: list | None = Field(default=None, sa_column=Column(JSON))

    learning_velocity: str = Field(default="steady")

    session_summaries: list | None = Field(default=None, sa_column=Column(JSON))
    next_focus: str = Field(default="")
    ready_for_next_dish: bool = Field(default=False)

    updated_at: datetime = Field(default_factory=datetime.utcnow)
