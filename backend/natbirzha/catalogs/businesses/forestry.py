"""Nine-step forestry career from raw logs to engineered building materials."""

from .career import career_business


def _forestry(
    business_id: str,
    name: str,
    order: int,
    open_cost: float,
    level: int,
    inputs: dict[str, float],
    outputs: dict[str, float],
    milestones: tuple[str, ...],
    *,
    prerequisite: str | None = None,
) -> dict:
    return career_business(
        business_id=business_id,
        name=name,
        icon="🌲" if order == 1 else "🪵",
        specialization="forester",
        order=order,
        open_cost=open_cost,
        level_required=level,
        inputs=inputs,
        outputs=outputs,
        milestones=milestones,
        milestone_resources=("steel", "lumber", "electronics"),
        description=f"Лесное производство: {name.lower()}.",
        prerequisites={prerequisite: min(50, 7 + order)} if prerequisite else None,
        territory_required=max(0, order - 1),
        starter=order == 1,
        tags=("forestry", "production", "materials"),
    )


FORESTRY_BUSINESSES = {
    spec["id"]: spec
    for spec in (
        _forestry(
            "forest_management_v2", "Лесозаготовительный комплекс", 1, 10_000, 1,
            {"fuel_diesel": 2, "energy": 2}, {"wood_raw": 60},
            ("Лесная дорога", "Механизированная вырубка", "Сортировочный склад",
             "Спутниковый учёт лесфонда", "Лесопромышленный кластер"),
        ),
        _forestry(
            "sawmill_v2", "Лесопильный завод", 2, 25_000, 3,
            {"wood_raw": 24, "energy": 5}, {"lumber": 18},
            ("Лесопильная линия", "Камерная сушка", "Сортировка пиломатериалов",
             "Безотходная распиловка", "Автоматический лесопильный комплекс"),
            prerequisite="forest_management_v2",
        ),
        _forestry(
            "pulp_plant_v2", "Целлюлозный комбинат", 3, 50_000, 6,
            {"wood_raw": 20, "water": 4, "energy": 7}, {"cellulose": 12},
            ("Подготовка щепы", "Варочный цех", "Очистка стоков",
             "Рекуперация реагентов", "Замкнутый целлюлозный цикл"),
            prerequisite="sawmill_v2",
        ),
        _forestry(
            "paper_mill_v2", "Бумажная фабрика", 4, 90_000, 9,
            {"cellulose": 18, "water": 5, "energy": 9}, {"paper": 13},
            ("Бумагоделательная машина", "Повторное использование воды", "Мелование бумаги",
             "Цифровой контроль полотна", "Высокопроизводительная бумажная линия"),
            prerequisite="pulp_plant_v2",
        ),
        _forestry(
            "packaging_factory_v2", "Картонно-упаковочный завод", 5, 160_000, 13,
            {"paper": 14, "energy": 10}, {"cardboard": 10},
            ("Гофроагрегат", "Печатный участок", "Формовка упаковки",
             "Переработка обрези", "Автоматизированный упаковочный кластер"),
            prerequisite="paper_mill_v2",
        ),
        _forestry(
            "furniture_factory_v2", "Мебельная фабрика", 6, 280_000, 18,
            {"lumber": 8, "steel": 1, "energy": 12}, {"furniture": 4},
            ("Мебельный цех", "Фурнитурная линия", "Покрасочная камера",
             "Модульная сборка", "Роботизированная мебельная фабрика"),
            prerequisite="packaging_factory_v2",
        ),
        _forestry(
            "engineered_wood_plant_v2", "Завод инженерной древесины", 7, 520_000, 24,
            {"lumber": 7, "basic_chem": 3, "energy": 16}, {"engineered_wood": 5},
            ("Слоёный брус", "Прессование панелей", "Влагостойкая пропитка",
             "Контроль прочности", "Инженерный древесный кластер"),
            prerequisite="furniture_factory_v2",
        ),
        _forestry(
            "wood_composite_plant_v2", "Завод древесных композитов", 8, 950_000, 30,
            {"lumber": 4, "cellulose": 2, "basic_chem": 4, "energy": 20},
            {"composite": 4},
            ("Древесное волокно", "Композитное прессование", "Огнестойкая связка",
             "Непрерывный контроль качества", "Композитный промышленный кластер"),
            prerequisite="engineered_wood_plant_v2",
        ),
        _forestry(
            "timber_module_factory_v2", "Завод деревянных модулей", 9, 1_600_000, 38,
            {"engineered_wood": 4, "concrete": 3, "steel": 2, "energy": 28},
            {"prefab_modules": 1.5},
            ("Раскрой домокомплектов", "Сборка стеновых панелей", "Инженерные коммуникации",
             "Автоматическая линия комплектации", "Кластер быстровозводимого строительства"),
            prerequisite="wood_composite_plant_v2",
        ),
    )
}
