from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class UserDishProgress(SQLModel, table=True):
    __tablename__ = "userdishprogress"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("user_id", "dish_id"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    dish_id: int = Field(foreign_key="dish.id")
    status: str = Field(default="not_started")
    started_at: datetime | None = None
    completed_at: datetime | None = None
