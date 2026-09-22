"""Metallurgy career converting mined ore into strategic materials."""

from .career import career_business


def _m(bid, name, icon, order, cost, level, inputs, outputs, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="metallurgist", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs=outputs,
        milestones=events, milestone_resources=("steel", "copper", "electronics"),
        description=f"Металлургическое предприятие: {name.lower()} с ростом выхода готового металла.",
        prerequisites=prerequisite, territory_required=max(1, order // 2), starter=starter,
        tags=("metallurgy", "processing"),
    )


METALLURGY_BUSINESSES = {
    spec["id"]: spec for spec in [
        _m("pig_iron_shop", "Чугунолитейный цех", "🔥", 1, 13_000, 1,
           {"iron_ore": 40, "coal": 16, "energy": 8, "water": 3}, {"steel": 20},
           ("Новая печь", "Шихтовый двор", "Система охлаждения", "Автодозирование", "Промышленный литейный цех"), starter=True),
        _m("steel_plant_v2", "Сталелитейный завод", "🏭", 2, 36_000, 5,
           {"iron_ore": 55, "coal": 20, "energy": 14, "water": 6}, {"steel": 34},
           ("Доменная печь", "Газоочистка", "Непрерывная разливка", "Роботизированный прокат", "Интегрированный сталелитейный комбинат"), prerequisite={"pig_iron_shop": 8}),
        _m("copper_smelter_v2", "Медеплавильный завод", "🟠", 3, 82_000, 9,
           {"copper_ore": 45, "energy": 18, "water": 5}, {"copper": 28},
           ("Плавильная печь", "Сероулавливание", "Электролизный цех", "Автоконтроль состава", "Медеплавильный кластер"), prerequisite={"steel_plant_v2": 10}),
        _m("aluminum_plant_v2", "Алюминиевый завод", "🪙", 4, 150_000, 13,
           {"bauxite": 55, "energy": 42, "basic_chem": 2}, {"aluminum": 30},
           ("Глинозёмный участок", "Электролизные ванны", "Литейная линия", "Энергосберегающая автоматика", "Алюминиевый мегакомплекс"), prerequisite={"copper_smelter_v2": 12}),
        _m("rolling_mill_v2", "Прокатный комбинат", "🏗️", 5, 260_000, 17,
           {"steel": 32, "energy": 15}, {"rolled_metal": 28},
           ("Нагревательная печь", "Черновая клеть", "Чистовая линия", "Автоматический контроль толщины", "Высокопроизводительный прокатный комбинат"), prerequisite={"steel_plant_v2": 20}),
        _m("nickel_plant", "Никелевый завод", "⚙️", 6, 480_000, 22,
           {"nickel_concentrate": 24, "energy": 25, "basic_chem": 2}, {"nickel_metal": 17},
           ("Обжиговый участок", "Выщелачивание", "Электролиз никеля", "Автоматическая очистка", "Никелевый металлургический кластер"), prerequisite={"aluminum_plant_v2": 18}),
        _m("special_steel_plant", "Завод специальных сталей", "🧪", 7, 800_000, 28,
           {"steel": 26, "nickel_metal": 6, "energy": 28}, {"superalloy": 13},
           ("Вакуумная печь", "Легирующий участок", "Термообработка", "Спектральный контроль", "Кластер специальных сталей"), prerequisite={"nickel_plant": 15, "rolling_mill_v2": 25}),
        _m("high_strength_materials", "Завод высокопрочных сплавов", "🛡️", 8, 1_350_000, 34,
           {"superalloy": 10, "rare_earths": 1, "energy": 30}, {"advanced_alloy": 8},
           ("Чистая плавильная зона", "Изостатическое прессование", "Прецизионный прокат", "Роботизированный контроль", "Высокопрочный сплавный кластер"), prerequisite={"special_steel_plant": 20}),
        _m("titanium_complex", "Титановый комплекс", "🛰️", 9, 2_400_000, 40,
           {"minerals": 25, "energy": 55, "basic_chem": 5}, {"titanium_alloy": 8},
           ("Хлоридный цех", "Губчатый титан", "Вакуумная плавка", "Прецизионная обработка", "Титановый промышленный кластер"), prerequisite={"high_strength_materials": 20}),
        _m("metallurgy_holding_v2", "Металлургический концерн", "🏙️", 10, 4_800_000, 48,
           {"iron_ore": 70, "coal": 24, "energy": 70, "water": 20}, {"steel": 45, "rolled_metal": 20, "superalloy": 6},
           ("Единый сырьевой двор", "Общая энергетика", "Центральная лаборатория", "Сквозная автоматизация", "Национальный металлургический концерн"), prerequisite={"titanium_complex": 20, "special_steel_plant": 30}),
    ]
}
