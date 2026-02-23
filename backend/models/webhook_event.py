from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class WebhookEvent(SQLModel, table=True):
    __tablename__ = "webhook_event"  # type: ignore[assignment]

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
