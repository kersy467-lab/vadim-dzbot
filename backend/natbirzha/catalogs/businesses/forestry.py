"""Forestry career starter for companies in the canonical forester branch."""

from .career import career_business


FORESTRY_BUSINESSES = {
    "forest_management_v2": career_business(
        business_id="forest_management_v2",
        name="Лесозаготовительный комплекс",
        icon="🌲",
        specialization="forester",
        order=1,
        open_cost=10_000,
        level_required=1,
        inputs={"fuel_diesel": 2, "energy": 2},
        outputs={"wood_raw": 60},
        milestones=(
            "Лесная дорога",
            "Механизированная вырубка",
            "Сортировочный склад",
            "Спутниковый учёт лесфонда",
            "Лесопромышленный кластер",
        ),
        milestone_resources=("steel", "lumber", "electronics"),
        description="Заготовка древесины для лесопилок и производств материалов.",
        starter=True,
        tags=("forestry", "production"),
    )
}
