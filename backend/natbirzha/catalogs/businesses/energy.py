"""Power career with fuel, renewable and nuclear generation strategies."""

from .career import career_business


def _e(bid, name, icon, order, cost, level, inputs, output, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="power_engineer", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs={"energy": output},
        milestones=events, milestone_resources=("steel", "copper", "electronics"),
        description=f"Энергетический объект: {name.lower()}. Производит электроэнергию для рынка.",
        prerequisites=prerequisite, territory_required=max(1, order // 2), starter=starter,
        tags=("energy", "utility"),
    )


ENERGY_BUSINESSES = {
    spec["id"]: spec for spec in [
        _e("diesel_power_station", "Дизельная электростанция", "⚡", 1, 11_000, 1,
           {"fuel_diesel": 5, "water": 1}, 85,
           ("Топливное хранилище", "Новый генератор", "Рекуперация тепла", "Цифровая диспетчерская", "Высокоэффективный энергокомплекс"), starter=True),
        _e("small_gas_chp", "Малая газовая ТЭЦ", "🔥", 2, 32_000, 4,
           {"gas_natural": 5, "water": 4}, 120,
           ("Газовая рампа", "Паровой контур", "Турбогенератор", "Интеллектуальное управление", "Комбинированный энергоблок"), prerequisite={"diesel_power_station": 8}),
        _e("wind_park_v2", "Ветровой парк", "💨", 3, 75_000, 8,
           {}, 75,
           ("Сервисная база", "Новые турбины", "Метеосистема", "Накопители энергии", "Региональный ветровой кластер"), prerequisite={"diesel_power_station": 12}),
        _e("solar_park_v2", "Солнечная электростанция", "☀️", 4, 110_000, 11,
           {}, 90,
           ("Новая секция панелей", "Система очистки", "Высокоэффективные инверторы", "Батарейный парк", "Солнечный энергокластер"), prerequisite={"wind_park_v2": 10}),
        _e("coal_tpp_v2", "Угольная ТЭС", "🏭", 5, 240_000, 15,
           {"coal": 18, "water": 10}, 260,
           ("Угольный склад", "Новая котельная система", "Турбогенератор", "Газоочистка и автоматика", "Сверхкритический энергоблок"), prerequisite={"small_gas_chp": 15}),
        _e("gas_turbine_v2", "Газотурбинная электростанция", "🔥", 6, 420_000, 20,
           {"gas_natural": 14, "water": 6}, 320,
           ("Компрессорная станция", "Новая турбина", "Утилизационный котёл", "Цифровой контроль", "Высокоэффективный ГТУ-кластер"), prerequisite={"small_gas_chp": 20}),
        _e("hydro_station_v2", "Гидроэлектростанция", "🌊", 7, 850_000, 26,
           {}, 360,
           ("Водосброс", "Машинный зал", "Новая турбина", "Автоматизация шлюзов", "Гидроэнергетический кластер"), prerequisite={"solar_park_v2": 20}),
        _e("storage_park", "Энергетический накопительный парк", "🔋", 8, 1_400_000, 32,
           {"batteries": 1}, 150,
           ("Первый батарейный блок", "Силовая электроника", "Балансирующая автоматика", "Роботизированный сервис", "Региональный накопительный парк"), prerequisite={"gas_turbine_v2": 20}),
        _e("combined_tpp", "Крупная комбинированная ТЭС", "🏙️", 9, 2_600_000, 38,
           {"gas_natural": 18, "coal": 12, "water": 16}, 620,
           ("Топливный узел", "Парогазовый контур", "Новый машинный зал", "Предиктивная автоматика", "Крупнейший тепловой кластер"), prerequisite={"coal_tpp_v2": 30, "gas_turbine_v2": 25}),
        _e("nuclear_station_v2", "Атомная электростанция", "☢️", 10, 6_500_000, 48,
           {"uranium_raw": 0.8, "water": 30}, 950,
           ("Техническое водоснабжение", "Хранилище топлива", "Модернизация турбин", "Цифровой контроль реактора", "Атомный энергокомплекс"), prerequisite={"combined_tpp": 30}),
    ]
}
