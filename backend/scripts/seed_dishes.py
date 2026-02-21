"""Seed the 3 Phase-1 starter dishes into the database.

Usage:
    uv run python -m backend.scripts.seed_dishes
"""

from sqlmodel import Session, select

from backend.core.database import engine
from backend.models.dish import Dish

STARTER_DISHES = [
    Dish(
        slug="fried-rice",
        name_ja="チャーハン",
        name_en="Fried Rice",
        description_ja=(
            "水分コントロールと高温調理をマスターする基礎料理。"
            "ご飯の水分を飛ばし、パラパラに仕上げる技術を習得します。"
        ),
        principles=["moisture_control", "heat_management", "oil_coating"],
        transferable_to=["minestrone", "ratatouille"],
        month_unlocked=1,
        order=1,
    ),
    Dish(
        slug="beef-steak",
        name_ja="ビーフステーキ",
        name_en="Beef Steak",
        description_ja=(
            "メイラード反応と肉の温度管理を学ぶ料理。"
            "表面の焼き色と内部の火加減のバランスを掴みます。"
        ),
        principles=["maillard_reaction", "temperature_control", "resting"],
        transferable_to=["pork_chop", "chicken_breast"],
        month_unlocked=1,
        order=2,
    ),
    Dish(
        slug="pomodoro",
        name_ja="ポモドーロ",
        name_en="Pasta al Pomodoro",
        description_ja=(
            "トマトの酸味と甘みのバランス、パスタの茹で方を学ぶ料理。"
            "シンプルな素材から深い味を引き出す技術を習得します。"
        ),
        principles=["acid_balance", "pasta_cooking", "sauce_reduction"],
        transferable_to=["arrabbiata", "amatriciana"],
        month_unlocked=1,
        order=3,
    ),
]


def seed() -> None:
    with Session(engine) as db:
        for dish in STARTER_DISHES:
            existing = db.exec(select(Dish).where(Dish.slug == dish.slug)).first()
            if existing is None:
                db.add(dish)
                print(f"Inserted: {dish.name_ja} ({dish.slug})")
            else:
                print(f"Skipped (already exists): {dish.slug}")
        db.commit()
    print("Done.")


if __name__ == "__main__":
    seed()
