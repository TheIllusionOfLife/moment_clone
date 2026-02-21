from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Dish(SQLModel, table=True):
    __tablename__ = "dish"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name_ja: str
    name_en: str
    description_ja: str
    principles: list | None = Field(default=None, sa_column=Column(JSON))
    transferable_to: list | None = Field(default=None, sa_column=Column(JSON))
    month_unlocked: int = Field(default=1)
    order: int
