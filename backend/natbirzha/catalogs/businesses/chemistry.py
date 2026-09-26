"""Chemical career supporting farming, water, mining and high-tech."""

from .career import career_business


def _c(bid, name, icon, order, cost, level, inputs, outputs, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="chemist", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs=outputs,
        milestones=events, milestone_resources=("steel", "electronics", "basic_chem"),
        description=f"Химическое производство: {name.lower()} для межотраслевых цепочек.",
        prerequisites=prerequisite, territory_required=max(1, order // 3), starter=starter,
        tags=("chemistry", "processing"),
    )


CHEMISTRY_BUSINESSES = {
    spec["id"]: spec for spec in [
        _c("fertilizer_factory_v2", "Завод минеральных удобрений", "🌱", 1, 11_000, 1,
           {"gas_natural": 6, "energy": 5, "water": 2}, {"fertilizer": 32},
           ("Смесительная линия", "Реактор синтеза", "Автодозировка", "Лаборатория состава", "Агрохимический кластер"), starter=True),
        _c("reagent_factory_v2", "Завод промышленных реагентов", "🧪", 2, 28_000, 5,
           {"oil_crude": 10, "energy": 7, "water": 3}, {"basic_chem": 26},
           ("Реакторный блок", "Очистка сырья", "Фракционирование", "Автоконтроль рецептуры", "Промышленный реагентный кластер"), prerequisite={"fertilizer_factory_v2": 8}),
        _c("acid_alkali_plant", "Производство кислот и щелочей", "⚗️", 3, 68_000, 9,
           {"basic_chem": 10, "energy": 10, "water": 5}, {"basic_chem": 18, "industrial_gases": 4},
           ("Кислотный цех", "Щелочная линия", "Коррозионная защита", "Автоматизация дозировки", "Кислотно-щелочной химкластер"), prerequisite={"reagent_factory_v2": 12}),
        _c("polymer_factory_v2", "Полимерный завод", "🧴", 4, 135_000, 13,
           {"oil_crude": 20, "gas_natural": 8, "energy": 14}, {"plastics": 24},
           ("Полимеризационный реактор", "Экструзионная линия", "Стабилизаторы", "Цифровой контроль качества", "Полимерный мегакомплекс"), prerequisite={"reagent_factory_v2": 18}),
        _c("lubricant_factory_v2", "Завод технических масел", "🛢️", 5, 240_000, 18,
           {"oil_crude": 24, "basic_chem": 4, "energy": 12}, {"lubricants": 18},
           ("Базовые масла", "Пакет присадок", "Фильтрационная линия", "Лаборатория вязкости", "Кластер технических масел"), prerequisite={"polymer_factory_v2": 15}),
        _c("synthetic_materials", "Завод синтетических материалов", "🧬", 6, 460_000, 23,
           {"plastics": 18, "composite": 2, "basic_chem": 6, "energy": 18}, {"advanced_composite": 10},
           ("Композитная линия", "Армирование материала", "Высокотемпературная печь", "Робоконтроль", "Синтетический материал-кластер"), prerequisite={"polymer_factory_v2": 25}),
        _c("battery_chemistry", "Аккумуляторная химия", "🔋", 7, 850_000, 29,
           {"lithium_raw": 7, "cobalt_raw": 3, "basic_chem": 5, "energy": 22}, {"lithium_pure": 8, "electrolyte": 10},
           ("Очистка лития", "Катодный участок", "Электролитная линия", "Сухая производственная зона", "Аккумуляторный химкластер"), prerequisite={"synthetic_materials": 18}),
        _c("high_purity_reagents", "Производство высокочистых реагентов", "🔬", 8, 1_600_000, 36,
           {"basic_chem": 18, "bio_raw": 1.5, "ultrapure_water": 10, "energy": 28}, {"bioreagent": 12, "catalyst": 6},
           ("Чистая лаборатория", "Молекулярная фильтрация", "Сверхчистая фасовка", "Контроль примесей", "Высокочистый химический кластер"), prerequisite={"battery_chemistry": 20}),
        _c("chemical_concern_v2", "Химический концерн", "🏙️", 9, 3_400_000, 45,
           {"oil_crude": 30, "gas_natural": 20, "energy": 42, "water": 16}, {"basic_chem": 32, "plastics": 18, "catalyst": 4},
           ("Центральный сырьевой парк", "Единая очистка", "Корпоративный R&D", "Сквозная автоматизация", "Межотраслевой химический концерн"), prerequisite={"high_purity_reagents": 25}),
    ]
}
