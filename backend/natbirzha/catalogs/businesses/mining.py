"""Long-form mining career: mass ores -> precious -> strategic materials."""

from .career import career_business


def _m(bid, name, icon, order, cost, level, inputs, outputs, events, *, prerequisite=None, territory=1, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="miner", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs=outputs,
        milestones=events, milestone_resources=("steel", "lumber", "electronics"),
        description=f"Развитие добычи: {name.lower()} от малого объекта до промышленного кластера.",
        prerequisites=prerequisite, territory_required=territory, starter=starter,
        tags=("extraction", "mining"),
    )


MINING_BUSINESSES = {
    spec["id"]: spec for spec in [
        _m("coal_open_pit", "Угольный разрез", "🪨", 1, 12_000, 1,
           {"energy": 8, "water": 4, "fuel_diesel": 2, "food": 1}, {"coal": 100},
           ("Рабочая столовая", "Дренаж карьера", "Парк карьерных самосвалов", "Посёлок рабочих", "Автоматизированный угольный комплекс"), starter=True),
        _m("iron_quarry", "Железорудный карьер", "⛏️", 2, 28_000, 4,
           {"energy": 12, "water": 6, "fuel_diesel": 3, "food": 1.2}, {"iron_ore": 82},
           ("Дробильная линия", "Железнодорожная ветка", "Тяжёлая буровая техника", "Обогатительная фабрика", "Роботизированный ГОК"), prerequisite={"coal_open_pit": 8}, territory=2),
        _m("copper_quarry", "Медный карьер", "🟠", 3, 65_000, 7,
           {"energy": 18, "water": 8, "fuel_diesel": 4, "food": 1.5}, {"copper_ore": 55},
           ("Высоковольтная подстанция", "Система водоотведения", "Флотационная линия", "Глубокие горизонты", "Цифровой медный комплекс"), prerequisite={"iron_quarry": 10}, territory=2),
        _m("bauxite_quarry", "Бокситовый карьер", "🧱", 4, 120_000, 10,
           {"energy": 20, "water": 8, "fuel_diesel": 6, "food": 1.8}, {"bauxite": 75, "minerals": 18},
           ("Ремонтный ангар", "Конвейерная система", "Новый карьерный уступ", "Сортировочный комплекс", "Бокситовый мегакарьер"), prerequisite={"copper_quarry": 10}, territory=3),
        _m("silver_mine", "Серебряный рудник", "🥈", 5, 220_000, 14,
           {"energy": 25, "water": 9, "fuel_diesel": 5, "food": 2}, {"silver_ore": 24},
           ("Вентиляционная шахта", "Подземный подъёмник", "Укрепление тоннелей", "Обогатительный цех", "Автоматизированный серебряный рудник"), prerequisite={"copper_quarry": 20}, territory=3),
        _m("gold_mine", "Золотой рудник", "🥇", 6, 420_000, 18,
           {"energy": 30, "water": 10, "fuel_diesel": 6, "food": 2.2}, {"gold_ore": 12},
           ("Защищённое хранилище", "Новая смена и жилой лагерь", "Глубокое бурение", "Автоматическая сортировка", "Золотодобывающий кластер"), prerequisite={"silver_mine": 20}, territory=4),
        _m("nickel_gok", "Никелевый ГОК", "⚙️", 7, 750_000, 23,
           {"energy": 45, "water": 18, "basic_chem": 2, "fuel_diesel": 7}, {"nickel_concentrate": 20},
           ("Реагентный участок", "Очистка сточных вод", "Линия обогащения", "Автоматизированная дробилка", "Никелевый мегакомплекс"), prerequisite={"bauxite_quarry": 25}, territory=5),
        _m("diamond_mine", "Алмазный рудник", "💎", 8, 1_200_000, 28,
           {"energy": 40, "water": 12, "fuel_diesel": 7, "food": 2.5}, {"diamonds": 5},
           ("Сортировочный участок", "Усиленная охрана", "Рентген-сортировка", "Глубокая шахта", "Автоматический алмазный кластер"), prerequisite={"gold_mine": 25}, territory=5),
        _m("lithium_quarry_v2", "Литиевый карьер", "🔋", 9, 1_800_000, 32,
           {"energy": 55, "water": 35, "basic_chem": 3, "fuel_diesel": 8}, {"lithium_raw": 12},
           ("Водный резерв", "Насосная инфраструктура", "Переработка рассола", "Рециркуляция воды", "Литиевый промышленный кластер"), prerequisite={"nickel_gok": 20}, territory=6),
        _m("cobalt_mine_v2", "Кобальтовый рудник", "🔷", 10, 2_800_000, 38,
           {"energy": 62, "water": 24, "basic_chem": 5, "food": 3}, {"cobalt_raw": 8},
           ("Очистные сооружения", "Защищённая химическая зона", "Высокоточная сортировка", "Роботизация добычи", "Кобальтовый технологический комплекс"), prerequisite={"lithium_quarry_v2": 20}, territory=6),
        _m("rare_earth_complex_v2", "Редкоземельный комплекс", "✨", 11, 4_800_000, 45,
           {"energy": 85, "water": 32, "basic_chem": 8, "food": 3.5}, {"rare_earths": 6},
           ("Химическая лаборатория", "Разделение концентратов", "Чистая производственная зона", "Высокоточная сепарация", "Стратегический РЗМ-кластер"), prerequisite={"cobalt_mine_v2": 20}, territory=7),
        _m("uranium_complex_v2", "Урановый горнодобывающий комплекс", "☢️", 12, 7_500_000, 52,
           {"energy": 100, "water": 45, "basic_chem": 10, "food": 4}, {"uranium_raw": 4},
           ("Радиационный контроль", "Спецхранилище", "Защищённая транспортировка", "Глубокая переработка руды", "Национальный урановый комплекс"), prerequisite={"rare_earth_complex_v2": 25}, territory=8),
    ]
}
