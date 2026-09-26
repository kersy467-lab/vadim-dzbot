"""Agricultural career with feed, food and high-intensity greenhouse chains."""

from .career import career_business


def _a(bid, name, icon, order, cost, level, inputs, outputs, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="agrarian", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs=outputs,
        milestones=events, milestone_resources=("lumber", "steel", "electronics"),
        description=f"Аграрное предприятие: {name.lower()} с постепенной механизацией и автоматизацией.",
        prerequisites=prerequisite, territory_required=max(1, order // 2), starter=starter,
        tags=("agriculture", "food"),
    )


AGRICULTURE_BUSINESSES = {
    spec["id"]: spec for spec in [
        _a("grain_farm_v2", "Зерновое хозяйство", "🌾", 1, 10_000, 1,
           {"water": 8, "fuel_diesel": 1.5, "energy": 2}, {"grain": 70},
           ("Система орошения", "Машинно-тракторный парк", "Собственный элеватор", "Агролаборатория", "Автономный агрокомплекс"), starter=True),
        _a("dairy_farm_v2", "Молочная ферма", "🥛", 2, 25_000, 4,
           {"grain": 12, "water": 10, "energy": 3}, {"milk": 35},
           ("Новый коровник", "Автокормление", "Охлаждение молока", "Ветеринарный комплекс", "Роботизированная молочная ферма"), prerequisite={"grain_farm_v2": 8}),
        _a("poultry_farm_v2", "Птицеферма", "🐔", 3, 48_000, 7,
           {"grain": 15, "water": 6, "energy": 5}, {"food": 18},
           ("Кормовой склад", "Вентиляция корпусов", "Автолиния кормления", "Перерабатывающий участок", "Птицеводческий комплекс"), prerequisite={"grain_farm_v2": 10}),
        _a("vegetable_farm_v2", "Овощное хозяйство", "🥕", 4, 85_000, 10,
           {"water": 18, "fertilizer": 2, "fuel_diesel": 2}, {"fresh_food": 28},
           ("Капельное орошение", "Овощехранилище", "Сортировочная линия", "Контроль почвы", "Высокопродуктивный овощной кластер"), prerequisite={"grain_farm_v2": 15}),
        _a("livestock_v2", "Животноводческий комплекс", "🐄", 5, 150_000, 14,
           {"grain": 24, "water": 16, "energy": 6}, {"meat": 16},
           ("Кормовой корпус", "Ветеринарная станция", "Холодильный склад", "Автоматизация кормления", "Животноводческий кластер"), prerequisite={"dairy_farm_v2": 15}),
        _a("oilseed_farm", "Масличное хозяйство", "🌻", 6, 260_000, 18,
           {"water": 16, "fertilizer": 3, "fuel_diesel": 3}, {"bio_raw": 25},
           ("Семенной фонд", "Новая уборочная техника", "Сушильный комплекс", "Анализ урожайности", "Масличный агрокластер"), prerequisite={"vegetable_farm_v2": 15}),
        _a("sugar_farm", "Сахарное хозяйство", "🍬", 7, 420_000, 23,
           {"water": 22, "fertilizer": 4, "fuel_diesel": 4}, {"sugar_raw": 24},
           ("Мелиорация полей", "Свеклопогрузочный парк", "Склад сырья", "Автосортировка", "Сахарный агрокластер"), prerequisite={"oilseed_farm": 15}),
        _a("greenhouse_v2", "Тепличный комбинат", "🍅", 8, 780_000, 28,
           {"water": 28, "energy": 35, "fertilizer": 5, "bioreagent": 1}, {"fresh_food": 42},
           ("Климатическая автоматика", "Гидропоника", "Светодиодное освещение", "Роботизированный сбор", "Круглогодичный тепличный кластер"), prerequisite={"vegetable_farm_v2": 25}),
        _a("food_processing_v2", "Агроперерабатывающий комбинат", "🥫", 9, 1_250_000, 34,
           {"grain": 18, "meat": 8, "milk": 8, "sugar_raw": 6, "fresh_food": 4, "energy": 24}, {"food": 45},
           ("Линия упаковки", "Холодовая цепь", "Контроль качества", "Автоматический склад", "Пищевой мегакомбинат"), prerequisite={"livestock_v2": 25, "greenhouse_v2": 20}),
        _a("agro_holding_v2", "Агропромышленный холдинг", "🌱", 10, 3_500_000, 45,
           {"water": 45, "energy": 32, "fertilizer": 8, "fuel_diesel": 8}, {"grain": 60, "food": 35},
           ("Единый снабженческий центр", "Региональные элеваторы", "Собственная лаборатория", "Роботизированные хозяйства", "Национальный агрохолдинг"), prerequisite={"food_processing_v2": 30}),
    ]
}
