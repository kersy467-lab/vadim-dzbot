"""Oil and gas career: extraction, refining and petrochemistry."""

from .career import career_business


def _o(bid, name, icon, order, cost, level, inputs, outputs, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="oilman", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs=outputs,
        milestones=events, milestone_resources=("steel", "electronics", "basic_chem"),
        description=f"Нефтегазовое предприятие: {name.lower()} от добычи до глубокой переработки.",
        prerequisites=prerequisite, territory_required=max(1, order // 2), starter=starter,
        tags=("oil_gas", "fuel"),
    )


OIL_GAS_BUSINESSES = {
    spec["id"]: spec for spec in [
        _o("small_oil_well_v2", "Малая нефтяная скважина", "🛢️", 1, 12_000, 1,
           {"energy": 5, "water": 2, "fuel_diesel": 1}, {"oil_crude": 60},
           ("Новая насос-качалка", "Резервуарный парк", "Подготовка нефти", "Автоматизация добычи", "Промышленный нефтепромысел"), starter=True),
        _o("gas_well_v2", "Газовая скважина", "🔥", 2, 30_000, 4,
           {"energy": 6, "water": 2}, {"gas_natural": 48},
           ("Компрессор", "Очистка газа", "Газосборный коллектор", "Автокомпрессорная", "Крупный газовый промысел"), prerequisite={"small_oil_well_v2": 8}),
        _o("oil_field_v2", "Нефтяное месторождение", "⛽", 3, 72_000, 8,
           {"energy": 10, "water": 4, "fuel_diesel": 2}, {"oil_crude": 115},
           ("Куст скважин", "Система сбора нефти", "Дожимная станция", "Цифровое месторождение", "Крупный нефтепромысел"), prerequisite={"small_oil_well_v2": 15}),
        _o("gas_processing_v2", "Газоперерабатывающая станция", "🧊", 4, 140_000, 12,
           {"gas_natural": 55, "energy": 10}, {"lng": 30},
           ("Осушка газа", "Фракционирование", "Компрессорный парк", "Контроль качества", "Интегрированный ГПЗ"), prerequisite={"gas_well_v2": 15}),
        _o("refinery_v2", "Нефтеперерабатывающий завод", "🏭", 5, 300_000, 16,
           {"oil_crude": 80, "energy": 18, "water": 8}, {"fuel_diesel": 38, "gasoline": 24},
           ("Атмосферная перегонка", "Вакуумная установка", "Каталитический крекинг", "Глубокая переработка", "Интегрированный НПЗ"), prerequisite={"oil_field_v2": 20}),
        _o("diesel_complex_v2", "Дизельный комплекс", "🚛", 6, 520_000, 21,
           {"oil_crude": 65, "energy": 16, "catalyst": 1}, {"fuel_diesel": 55},
           ("Гидроочистка", "Новый реактор", "Стабилизация топлива", "Автоконтроль качества", "Крупный дизельный кластер"), prerequisite={"refinery_v2": 15}),
        _o("aviation_fuel_v2", "Производство авиационного топлива", "✈️", 7, 880_000, 27,
           {"oil_crude": 62, "energy": 22, "catalyst": 2}, {"jet_fuel": 42},
           ("Керосиновая фракция", "Гидроочистка", "Лаборатория качества", "Защищённый резервуарный парк", "Авиационный топливный кластер"), prerequisite={"refinery_v2": 25}),
        _o("petrochemical_complex_v2", "Нефтехимический комплекс", "🧪", 8, 1_500_000, 33,
           {"oil_crude": 45, "gas_natural": 20, "energy": 30}, {"plastics": 32, "basic_chem": 10},
           ("Пиролизная установка", "Полимеризационный блок", "Газофракционирование", "Автоматизация реакторов", "Нефтехимический мегакластер"), prerequisite={"refinery_v2": 30}),
        _o("large_gas_field", "Крупное газовое месторождение", "🔥", 9, 2_500_000, 39,
           {"energy": 40, "water": 8}, {"gas_natural": 190},
           ("Новая кустовая площадка", "Магистральный коллектор", "Компрессорный цех", "Цифровая добыча", "Газодобывающий мегапромысел"), prerequisite={"gas_processing_v2": 30}),
        _o("offshore_platform_v2", "Шельфовая платформа", "🌊", 10, 5_500_000, 48,
           {"energy": 65, "fuel_diesel": 8, "food": 4}, {"oil_crude": 150, "gas_natural": 75},
           ("Морская база снабжения", "Подводные трубопроводы", "Новый буровой модуль", "Безлюдная платформа", "Шельфовый нефтегазовый кластер"), prerequisite={"petrochemical_complex_v2": 25, "large_gas_field": 20}),
    ]
}
