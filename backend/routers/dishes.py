from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from backend.core.auth import get_current_user
from backend.core.database import get_async_session
from backend.models.dish import Dish
from backend.models.user import User
from backend.models.user_dish_progress import UserDishProgress

router = APIRouter(prefix="/api/dishes", tags=["dishes"])


@router.get("/")
async def list_dishes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    dishes = (await db.execute(select(Dish).order_by(col(Dish.order)))).scalars().all()
    # Fetch all progress rows in one query to avoid N+1
    progress_rows = (
        (
            await db.execute(
                select(UserDishProgress).where(UserDishProgress.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    progress_map = {p.dish_id: p for p in progress_rows}
    return [_dish_with_progress(d, progress_map.get(d.id)) for d in dishes]  # type: ignore[arg-type]


@router.get("/{slug}/")
async def get_dish(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    dish = (await db.execute(select(Dish).where(Dish.slug == slug))).scalars().first()
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    progress = (
        (
            await db.execute(
                select(UserDishProgress).where(
                    UserDishProgress.user_id == current_user.id,
                    UserDishProgress.dish_id == dish.id,
                )
            )
        )
        .scalars()
        .first()
    )
    return _dish_with_progress(dish, progress)


def _dish_with_progress(dish: Dish, progress: UserDishProgress | None) -> dict:
    return {
        "id": dish.id,
        "slug": dish.slug,
        "name_ja": dish.name_ja,
        "name_en": dish.name_en,
        "description_ja": dish.description_ja,
        "principles": dish.principles or [],
        "transferable_to": dish.transferable_to or [],
        "month_unlocked": dish.month_unlocked,
        "order": dish.order,
        "progress": {
            "status": progress.status if progress else "not_started",
            "started_at": progress.started_at.isoformat()
            if progress and progress.started_at
            else None,
            "completed_at": progress.completed_at.isoformat()
            if progress and progress.completed_at
            else None,
        },
    }
