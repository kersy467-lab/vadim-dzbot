"""Construction career: materials first, then project capacity."""

from .career import career_business


def _b(bid, name, icon, order, cost, level, inputs, outputs, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="construction", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs=outputs,
        milestones=events, milestone_resources=("steel", "lumber", "electronics"),
        description=f"Строительное предприятие: {name.lower()} для инфраструктуры и корпоративных проектов.",
        prerequisites=prerequisite, territory_required=max(1, order // 3), starter=starter,
        tags=("construction", "infrastructure"),
    )


CONSTRUCTION_BUSINESSES = {
    spec["id"]: spec for spec in [
        _b("logging_site_v2", "Лесозаготовительный участок", "🌲", 1, 10_000, 1,
           {"fuel_diesel": 2, "energy": 2}, {"wood_raw": 60},
           ("Лесная дорога", "Новая техника", "Сортировочный склад", "Спутниковый учёт", "Механизированный лесной кластер"), starter=True),
        _b("lumber_mill_v2", "Лесопильный комбинат", "🪵", 2, 24_000, 4,
           {"wood_raw": 42, "energy": 6}, {"lumber": 30},
           ("Лесопильная линия", "Сушильная камера", "Сортировка пиломатериалов", "Автосклад", "Деревообрабатывающий кластер"), prerequisite={"logging_site_v2": 8}),
        _b("brick_factory", "Кирпичный завод", "🧱", 3, 52_000, 8,
           {"minerals": 30, "energy": 10, "fuel_diesel": 2}, {"brick": 28},
           ("Формовочная линия", "Новая печь", "Сушильный тоннель", "Роботизированная укладка", "Кирпичный промышленный комплекс"), prerequisite={"lumber_mill_v2": 10}),
        _b("cement_factory", "Цементный завод", "🏭", 4, 110_000, 12,
           {"minerals": 38, "coal": 8, "energy": 12}, {"cement": 26},
           ("Сырьевая мельница", "Вращающаяся печь", "Клинкерный склад", "Энергосберегающий помол", "Цементный мегакомбинат"), prerequisite={"brick_factory": 12}),
        _b("concrete_factory", "Бетонный завод", "🏗️", 5, 190_000, 16,
           {"cement": 20, "water": 12, "energy": 8}, {"concrete": 32},
           ("Бетонно-смесительный узел", "Силосный парк", "Новая рецептура", "Автодозирование", "Региональный бетонный кластер"), prerequisite={"cement_factory": 15}),
        _b("metal_structure_factory_v2", "Завод металлоконструкций", "🔩", 6, 360_000, 21,
           {"rolled_metal": 20, "energy": 14}, {"metal_structures": 16},
           ("Раскрой металла", "Сварочный участок", "Антикоррозионная линия", "Роботизированная сварка", "Кластер металлоконструкций"), prerequisite={"concrete_factory": 15}),
        _b("construction_company_v2", "Строительная компания", "👷", 7, 650_000, 27,
           {"concrete": 8, "lumber": 5, "fuel_diesel": 4}, {"construction_capacity": 18},
           ("Собственный парк техники", "Проектный офис", "Промышленная бригада", "Цифровой стройконтроль", "Региональный генподрядчик"), prerequisite={"metal_structure_factory_v2": 18}),
        _b("industrial_contractor", "Промышленный подрядчик", "🏭", 8, 1_250_000, 34,
           {"metal_structures": 8, "concrete": 10, "fuel_diesel": 6}, {"construction_capacity": 32},
           ("Монтажное управление", "Тяжёлые краны", "Инженерный штаб", "Модульное строительство", "Промышленный подрядный холдинг"), prerequisite={"construction_company_v2": 25}),
        _b("infrastructure_holding", "Инфраструктурный холдинг", "🌉", 9, 2_600_000, 42,
           {"metal_structures": 10, "concrete": 14, "electronics": 2, "fuel_diesel": 8}, {"construction_capacity": 55},
           ("Дорожный дивизион", "Сетевое строительство", "Терминальные проекты", "Единая цифровая стройка", "Национальный инфраструктурный холдинг"), prerequisite={"industrial_contractor": 30}),
    ]
}
