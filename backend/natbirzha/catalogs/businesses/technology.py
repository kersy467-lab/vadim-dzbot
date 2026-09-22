"""Technology career supplying automation and late-game electronics."""

from .career import career_business


def _t(bid, name, icon, order, cost, level, inputs, outputs, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="technoprom", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs=outputs,
        milestones=events, milestone_resources=("copper", "plastics", "electronics"),
        description=f"Технологическое предприятие: {name.lower()} для автоматизации и high-tech цепочек.",
        prerequisites=prerequisite, territory_required=max(1, order // 3), starter=starter,
        tags=("technology", "hightech"),
    )


TECHNOLOGY_BUSINESSES = {
    spec["id"]: spec for spec in [
        _t("electronics_workshop", "Электронная мастерская", "🔌", 1, 12_000, 1,
           {"copper": 10, "plastics": 4, "energy": 6}, {"components": 18},
           ("Чистый монтажный участок", "SMT-линия", "Контроль качества", "Автоматическая сборка", "Электронный производственный кластер"), starter=True),
        _t("electrical_factory", "Завод электротехники", "⚡", 2, 30_000, 5,
           {"copper": 14, "components": 6, "energy": 8}, {"electrical_equipment": 14, "machinery": 4},
           ("Обмоточный участок", "Силовая линия", "Испытательная лаборатория", "Робосборка", "Электротехнический кластер"), prerequisite={"electronics_workshop": 8}),
        _t("sensor_factory", "Производство датчиков", "📡", 3, 70_000, 9,
           {"components": 10, "copper": 5, "energy": 9}, {"sensors": 12},
           ("Калибровочная лаборатория", "Микромонтаж", "Защищённые корпуса", "Автокалибровка", "Сенсорный технологический кластер"), prerequisite={"electronics_workshop": 15}),
        _t("server_center_v2", "Серверный центр", "🖥️", 4, 145_000, 13,
           {"electronics": 3, "energy": 22, "water": 4}, {"cloud_compute": 8},
           ("Первый серверный зал", "Резервное питание", "Жидкостное охлаждение", "Оркестрация нагрузки", "Региональный вычислительный центр"), prerequisite={"sensor_factory": 12}),
        _t("automation_factory", "Завод промышленной автоматики", "🤖", 5, 280_000, 18,
           {"components": 12, "sensors": 6, "copper": 6, "energy": 15}, {"automation_systems": 10},
           ("ПЛК-линия", "Промышленная связь", "Стенд интеграции", "Роботизированная сборка", "Кластер промышленной автоматики"), prerequisite={"sensor_factory": 20}),
        _t("robotics_factory_v2", "Робототехнический завод", "🦾", 6, 520_000, 23,
           {"automation_systems": 6, "machinery": 5, "electronics": 4, "energy": 20}, {"robots": 6},
           ("Мехатронный участок", "Сервоприводы", "Машинное зрение", "Автосборочная линия", "Робототехнический кластер"), prerequisite={"automation_factory": 20}),
        _t("battery_system_factory", "Завод аккумуляторных систем", "🔋", 7, 900_000, 29,
           {"lithium_pure": 6, "cobalt_raw": 2, "electronics": 3, "energy": 20}, {"batteries": 8},
           ("Ячеечная линия", "BMS-производство", "Термоконтроль", "Робосборка модулей", "Аккумуляторный системный кластер"), prerequisite={"automation_factory": 25}),
        _t("microelectronics_complex", "Микроэлектронный комплекс", "💾", 8, 1_800_000, 36,
           {"rare_earths": 2, "gold_ore": 1, "ultrapure_water": 12, "energy": 34}, {"electronics": 10},
           ("Чистая зона", "Фотолитография", "Тонкоплёночный участок", "Автоконтроль пластин", "Микроэлектронный мегакомплекс"), prerequisite={"robotics_factory_v2": 20}),
        _t("ai_research_center", "Высокотехнологический исследовательский центр", "🧠", 9, 3_000_000, 43,
           {"electronics": 8, "cloud_compute": 4, "energy": 40}, {"ai_accelerator": 3},
           ("Вычислительная лаборатория", "Прототипирование", "Тестовый суперкомпьютер", "Автоматический дизайн", "Корпоративный R&D-кластер"), prerequisite={"microelectronics_complex": 25}),
        _t("technology_megacorp", "Технологическая мегакорпорация", "🌐", 10, 5_500_000, 50,
           {"electronics": 10, "rare_earths": 3, "ultrapure_water": 15, "energy": 55}, {"quantum_modules": 2, "automation_systems": 8},
           ("Корпоративная фабрика", "Собственная компонентная база", "Научный кампус", "Безлюдное производство", "Национальная технологическая мегакорпорация"), prerequisite={"ai_research_center": 30}),
    ]
}
