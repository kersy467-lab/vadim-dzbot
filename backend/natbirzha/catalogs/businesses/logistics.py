"""Logistics career producing transport capacity for large economic flows."""

from .career import career_business


def _l(bid, name, icon, order, cost, level, inputs, output, events, *, prerequisite=None, starter=False):
    return career_business(
        business_id=bid, name=name, icon=icon, specialization="logistics", order=order,
        open_cost=cost, level_required=level, inputs=inputs, outputs={"logistics_capacity": output},
        milestones=events, milestone_resources=("steel", "fuel_diesel", "electronics"),
        description=f"Логистический бизнес: {name.lower()} создаёт транспортную мощность для рынка.",
        prerequisites=prerequisite, territory_required=max(1, order // 3), starter=starter,
        tags=("logistics", "service"),
    )


LOGISTICS_BUSINESSES = {
    spec["id"]: spec for spec in [
        _l("courier_service_v2", "Курьерская служба", "📦", 1, 9_000, 1,
           {"fuel_diesel": 2, "gasoline": 1.5, "cardboard": 1}, 30,
           ("Первый гараж", "Маршрутная сеть", "Сортировочный пункт", "Мобильная диспетчеризация", "Городская курьерская сеть"), starter=True),
        _l("trucking_company_v2", "Автотранспортная компания", "🚚", 2, 25_000, 5,
           {"fuel_diesel": 6, "lubricants": 1}, 55,
           ("Грузовой парк", "Ремонтная база", "Дальние рейсы", "Телематика транспорта", "Региональный автоперевозчик"), prerequisite={"courier_service_v2": 8}),
        _l("regional_warehouse_v2", "Региональный склад", "🏬", 3, 58_000, 9,
           {"energy": 7}, 48,
           ("Стеллажный комплекс", "Погрузочная техника", "Адресное хранение", "Автоматический склад", "Региональный распределительный центр"), prerequisite={"trucking_company_v2": 10}),
        _l("freight_terminal_v2", "Грузовой терминал", "🏗️", 4, 120_000, 13,
           {"fuel_diesel": 5, "energy": 8}, 85,
           ("Контейнерная площадка", "Крановый парк", "Таможенная зона", "Автодиспетчеризация", "Крупный грузовой терминал"), prerequisite={"regional_warehouse_v2": 15}),
        _l("rail_operator_v2", "Железнодорожный оператор", "🚆", 5, 260_000, 18,
           {"energy": 12, "fuel_diesel": 5}, 135,
           ("Локомотивный парк", "Вагонное депо", "Сортировочная станция", "Цифровая маршрутизация", "Региональная грузовая железная дорога"), prerequisite={"freight_terminal_v2": 15}),
        _l("cold_chain_v2", "Холодильная логистика", "❄️", 6, 470_000, 23,
           {"energy": 18, "fuel_diesel": 5}, 105,
           ("Холодильный склад", "Рефрижераторный парк", "Температурный контроль", "Автомониторинг", "Холодовая логистическая сеть"), prerequisite={"regional_warehouse_v2": 25}),
        _l("tanker_logistics", "Нефтеналивной оператор", "🛢️", 7, 820_000, 29,
           {"fuel_diesel": 7, "energy": 10}, 150,
           ("Наливная эстакада", "Танкерный парк", "Система безопасности", "Автоконтроль маршрутов", "Региональный нефтеналивной оператор"), prerequisite={"rail_operator_v2": 20}),
        _l("container_terminal_v2", "Контейнерный терминал", "🚢", 8, 1_450_000, 35,
           {"energy": 20, "fuel_diesel": 8}, 220,
           ("Контейнерный двор", "Портальные краны", "Интермодальный узел", "Безлюдная перегрузка", "Контейнерный мегатерминал"), prerequisite={"rail_operator_v2": 28}),
        _l("seaport_v2", "Морской порт", "⚓", 9, 2_800_000, 42,
           {"energy": 28, "fuel_diesel": 12}, 330,
           ("Глубоководный причал", "Навалочный терминал", "Нефтеналивной причал", "Цифровой порт", "Международный морской хаб"), prerequisite={"container_terminal_v2": 25}),
        _l("air_freight_network", "Грузовая авиасеть", "✈️", 10, 5_000_000, 50,
           {"jet_fuel": 18, "energy": 24}, 420,
           ("Грузовой перрон", "Первый грузовой самолёт", "Авиационный терминал", "Автоматический хаб", "Международная грузовая авиасеть"), prerequisite={"seaport_v2": 25}),
    ]
}
