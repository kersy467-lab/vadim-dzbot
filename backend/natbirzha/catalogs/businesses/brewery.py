"""Beer, wine and aged-spirit production career."""

from .career import career_business


def _brewery(
    business_id: str,
    name: str,
    icon: str,
    order: int,
    open_cost: float,
    level: int,
    inputs: dict[str, float],
    output_id: str,
    output_rate: float,
    milestones: tuple[str, str, str, str, str],
    *,
    prerequisite: tuple[str, int] | None = None,
    starter: bool = False,
) -> dict:
    return career_business(
        business_id=business_id,
        name=name,
        icon=icon,
        specialization="brewery",
        order=order,
        open_cost=open_cost,
        level_required=level,
        inputs=inputs,
        outputs={output_id: output_rate},
        milestones=milestones,
        milestone_resources=(
            "steel", "lumber", "grain", "hops", "grapes", "wine", "energy", "water",
        ),
        description=f"Пивоваренная отрасль: {name.lower()} с поэтапной переработкой агросырья.",
        prerequisites={prerequisite[0]: prerequisite[1]} if prerequisite else None,
        territory_required=max(1, order // 2),
        starter=starter,
        tags=("brewery", "beverages", "food"),
    )


BREWERY_BUSINESSES = {
    spec["id"]: spec
    for spec in (
        _brewery(
            # This is deliberately a compact first plant. Once one firm from
            # each other sector exists, its hourly beer output is close to the
            # sum of all 11 starter plants' employee demand.
            "craft_brewery", "Ремесленная пивоварня", "🍺", 1, 2_000, 1,
            {"grain": 0.15, "hops": 0.015, "energy": 0.09, "water": 0.06},
            "beer", 6,
            ("Малый заторный чан", "Охлаждение сусла", "Фильтрационная линия",
             "Автоматический розлив", "Ремесленный пивоваренный комплекс"),
            starter=True,
        ),
        _brewery(
            "regional_brewery", "Региональная пивоварня", "🍺", 2, 32_000, 4,
            {"grain": 10, "hops": 1, "energy": 7, "water": 4},
            "beer", 10,
            ("Расширение варочного отделения", "Солодильный участок", "Холодильный склад",
             "Линия розлива", "Региональный пивоваренный кластер"),
            prerequisite=("craft_brewery", 8),
        ),
        _brewery(
            "industrial_brewery", "Промышленная пивоварня", "🍺", 3, 85_000, 8,
            {"grain": 18, "hops": 1.8, "energy": 14, "water": 7},
            "beer", 16,
            ("Крупный варочный цех", "Замкнутый контур воды", "Контроль брожения",
             "Высокоскоростной розлив", "Автоматизированный пивоваренный комбинат"),
            prerequisite=("regional_brewery", 12),
        ),
        _brewery(
            "grape_winery", "Винодельня", "🍷", 4, 180_000, 12,
            {"grapes": 4, "energy": 4, "water": 2},
            "wine", 2,
            ("Приём винограда", "Прессовый цех", "Контроль брожения",
             "Холодная стабилизация", "Автоматизированная винодельня"),
            prerequisite=("industrial_brewery", 15),
        ),
        _brewery(
            "regional_winery", "Региональный винный завод", "🍷", 5, 380_000, 17,
            {"grapes": 8, "energy": 9, "water": 4},
            "wine", 4,
            ("Сортировочная линия", "Резервуары брожения", "Лаборатория качества",
             "Линия розлива", "Региональный винодельческий комплекс"),
            prerequisite=("grape_winery", 18),
        ),
        _brewery(
            "sparkling_winery", "Завод игристых вин", "🍷", 6, 720_000, 23,
            {"grapes": 16, "energy": 18, "water": 8},
            "wine", 8,
            ("Вторичное брожение", "Купажный участок", "Контроль давления",
             "Автоматическая дегоржажная линия", "Крупный завод игристых вин"),
            prerequisite=("regional_winery", 21),
        ),
        _brewery(
            "cognac_distillery", "Коньячный дистилляционный завод", "🥃", 7, 1_300_000, 30,
            {"wine": 2, "energy": 8, "water": 1},
            "aged_spirits", 0.5,
            ("Винный дистиллятор", "Контур теплообмена", "Лаборатория дистилляции",
             "Линия выдержки", "Коньячный дистилляционный комплекс"),
            prerequisite=("sparkling_winery", 24),
        ),
        _brewery(
            "aged_cognac_house", "Дом выдержанного коньяка", "🥃", 8, 2_300_000, 38,
            {"wine": 4, "energy": 16, "water": 2},
            "aged_spirits", 1,
            ("Дубовые бочки", "Климатический погреб", "Контроль купажа",
             "Автоматизация учёта выдержки", "Комплекс выдержанного коньяка"),
            prerequisite=("cognac_distillery", 27),
        ),
        _brewery(
            "premium_cognac_house", "Премиальная коньячная мануфактура", "🥃", 9, 3_900_000, 46,
            {"wine": 8, "energy": 32, "water": 4},
            "aged_spirits", 2,
            ("Селекция спиртов", "Погреб длительной выдержки", "Мастерская купажа",
             "Премиальная линия розлива", "Премиальный коньячный дом"),
            prerequisite=("aged_cognac_house", 30),
        ),
        _brewery(
            "heritage_cognac_estate", "Коньячное наследственное хозяйство", "🥃", 10, 6_200_000, 55,
            {"wine": 14, "energy": 50, "water": 7},
            "aged_spirits", 3.5,
            ("Исторические подвалы", "Отбор редких спиртов", "Система микроклимата",
             "Коллекционная фасовка", "Наследственное коньячное хозяйство"),
            prerequisite=("premium_cognac_house", 33),
        ),
        _brewery(
            "cognac_export_complex", "Экспортный коньячный комплекс", "🥃", 11, 9_500_000, 60,
            {"wine": 24, "energy": 80, "water": 12},
            "aged_spirits", 6,
            ("Экспортный погреб", "Международная сертификация", "Линия коллекционных серий",
             "Автоматизация экспортных партий", "Экспортный коньячный концерн"),
            prerequisite=("heritage_cognac_estate", 36),
        ),
    )
}


__all__ = ["BREWERY_BUSINESSES"]
