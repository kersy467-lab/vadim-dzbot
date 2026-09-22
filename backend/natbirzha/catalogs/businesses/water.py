"""Water utility career from wells to semiconductor-grade water."""

from .career import career_business


def _w(bid, name, icon, order, cost, level, inputs, outputs, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="water", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs=outputs,
        milestones=events, milestone_resources=("steel", "basic_chem", "electronics"),
        description=f"Водная инфраструктура: {name.lower()} для снабжения промышленности.",
        prerequisites=prerequisite, territory_required=max(1, order // 3), starter=starter,
        tags=("water", "utility"),
    )


WATER_BUSINESSES = {
    spec["id"]: spec for spec in [
        _w("artesian_well", "Артезианская скважина", "💧", 1, 9_000, 1, {"energy": 2}, {"water": 100},
           ("Новая насосная группа", "Резервуар", "Фильтрационная система", "Автодиспетчеризация", "Промышленный узел водоснабжения"), starter=True),
        _w("pump_station_v2", "Насосная станция", "🚰", 2, 24_000, 4, {"energy": 5}, {"water": 150},
           ("Второй насосный блок", "Магистральный коллектор", "Частотные приводы", "Дистанционный контроль", "Региональная насосная станция"), prerequisite={"artesian_well": 8}),
        _w("water_treatment", "Станция водоочистки", "🧪", 3, 58_000, 8, {"water": 80, "basic_chem": 1, "energy": 8}, {"clean_water": 68},
           ("Механическая очистка", "Реагентный блок", "Мембранная фильтрация", "Контроль качества", "Комплекс глубокой очистки"), prerequisite={"pump_station_v2": 10}),
        _w("industrial_waterworks", "Промышленный водоканал", "🏭", 4, 120_000, 12, {"energy": 12, "basic_chem": 1.5}, {"water": 260},
           ("Промышленный резервуар", "Новая магистраль", "Насосная каскадная станция", "Система утечек", "Городской промышленный водоканал"), prerequisite={"pump_station_v2": 18}),
        _w("water_reservoir", "Водохранилище", "🌊", 5, 230_000, 17, {"energy": 3}, {"water": 180},
           ("Первая дамба", "Берегоукрепление", "Насосный узел", "Диспетчеризация", "Региональное водохранилище"), prerequisite={"industrial_waterworks": 15}),
        _w("deep_water_treatment", "Комплекс глубокой очистки", "🧼", 6, 430_000, 22, {"water": 120, "basic_chem": 3, "energy": 16}, {"clean_water": 108},
           ("Угольная фильтрация", "Озонирование", "Обратный осмос", "Лаборатория качества", "Глубокая многоступенчатая очистка"), prerequisite={"water_treatment": 25}),
        _w("desalination_complex", "Опреснительный комплекс", "🌐", 7, 900_000, 30, {"energy": 45, "basic_chem": 4}, {"water": 300},
           ("Забор морской воды", "Предочистка", "Мембранные каскады", "Энергорекуперация", "Крупный опреснительный кластер"), prerequisite={"deep_water_treatment": 20}),
        _w("ultrapure_water_plant", "Станция сверхчистой воды", "🔬", 8, 1_800_000, 38, {"clean_water": 70, "basic_chem": 5, "energy": 35}, {"ultrapure_water": 45},
           ("Предварительная фильтрация", "Обратный осмос", "Ионный обмен", "УФ-очистка", "Комплекс сверхчистой технологической воды"), prerequisite={"deep_water_treatment": 30}),
        _w("regional_water_operator", "Региональная водная система", "🏙️", 9, 3_600_000, 46, {"energy": 50, "basic_chem": 5}, {"water": 480, "clean_water": 90},
           ("Единый диспетчерский центр", "Межрайонные магистрали", "Резервные станции", "Предиктивное управление", "Региональный водный оператор"), prerequisite={"ultrapure_water_plant": 25}),
    ]
}
