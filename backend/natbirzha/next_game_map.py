"""Territorial views over the existing, persistent 2.0 industry graph."""

from collections import defaultdict


TERRITORY_NAMES = {
    "resources": (
        "Рудные предгорья", "Северный сырьевой пояс", "Промышленная долина",
        "Агропояс", "Обогатительный округ", "Металлургический кластер",
        "Биоресурсная территория", "Редкометалльный центр", "Орбитальный форпост",
    ),
    "energy": (
        "Тепловой узел", "Энергетическая долина", "Ветровой рубеж",
        "Гидроэнергетический каскад", "Водородный пояс", "Сетевая агломерация",
        "Автономный энергокластер", "Термоядерный центр", "Единая энергосистема",
    ),
    "oilgas": (
        "Нефтяной район", "Газовый бассейн", "Топливный пояс", "Нефтехимическая долина",
        "Криогенный узел", "Полимерный округ", "Биотехнологический пояс",
        "Центр замкнутой химии", "Орбитальный топливный комплекс",
    ),
    "materials": (
        "Рудный промышленный пояс", "Металлургический район", "Стальной узел",
        "Строительный округ", "Лесопромышленная территория", "Машиностроительный кластер",
        "Сплавной пояс", "Аккумуляторный центр", "Орбитальная верфь",
    ),
    "infrastructure": (
        "Строительный участок", "Транспортный узел", "Городской пояс",
        "Региональный логистический округ", "Торговая агломерация", "Портовый кластер",
        "Скоростной коридор", "Орбитальная инфраструктура", "Национальная сеть",
    ),
    "technology": (
        "Технологический кампус", "Электронный пояс", "Инженерный округ",
        "Центр вычислений", "Промышленная цифровая долина", "Квантовый кластер",
        "Сеть автономных систем", "Научный облачный центр", "Орбитальная лаборатория",
    ),
    "bank": (
        "Городской финансовый квартал", "Региональный банковский пояс", "Кредитный округ",
        "Расчётный узел", "Промышленный финансовый центр", "Инвестиционная территория",
        "Товарная биржевая зона", "Международный клиринг", "Орбитальный резервный центр",
    ),
}


def _branch_index(catalog):
    return {
        branch["id"]: {**branch, "sector_id": sector["id"], "sector_name": sector["name"]}
        for sector in catalog
        for branch in sector["branches"]
    }


def build_progression_map(
    sector_id, catalog, *, branch_path, facility_levels, company_level,
    consumed_branch_ids=(),
):
    """Build all industry maps without changing saved route or factory state."""
    sectors = {sector["id"]: sector for sector in catalog}
    if sector_id not in sectors:
        raise ValueError("Отрасль отсутствует на карте 2.0")

    branches = _branch_index(catalog)
    path = list(branch_path or [])
    consumed = set(consumed_branch_ids or [])
    current_branch_id = path[-1] if path and path[-1] in branches else None
    next_ids = set()
    if current_branch_id and (
        int(facility_levels.get(current_branch_id, 0)) > 0 or current_branch_id in consumed
    ):
        next_ids.update(branches[current_branch_id].get("next_branch_ids", []))

    first_id = path[0] if path and path[0] in branches else None
    revealed = bool(first_id and int(facility_levels.get(first_id, 0)) >= 8)
    route_positions = {branch_id: index for index, branch_id in enumerate(path)}
    map_sectors = []
    for sector in catalog:
        grouped = defaultdict(list)
        for branch in sector["branches"]:
            tier = min(9, max(1, int(branch.get("tier", 1))))
            state = (
                "merged" if branch["id"] in consumed
                else "built" if int(facility_levels.get(branch["id"], 0)) > 0
                else "opened" if branch["id"] in route_positions
                else "available" if branch["id"] in next_ids and int(company_level or 1) >= max(
                    len(path) + 1, int(branch.get("requirements", {}).get("company_level", 1)),
                )
                else "locked"
            )
            grouped[tier].append({
                "id": branch["id"], "name": branch["name"],
                "facility_name": branch["factory"]["facility_name"],
                "outputs": branch["outputs"], "tier": tier,
                "state": state, "facility_level": int(facility_levels.get(branch["id"], 0)),
                "required_company_level": max(
                    len(path) + 1, int(branch.get("requirements", {}).get("company_level", 1)),
                ),
                "next_branch_ids": list(branch.get("next_branch_ids", [])),
                "sector_id": sector["id"],
            })

        territories = []
        for tier, name in enumerate(TERRITORY_NAMES[sector["id"]], start=1):
            facilities = grouped.get(tier, [])
            reached_positions = [route_positions[row["id"]] for row in facilities
                                 if row["id"] in route_positions]
            is_current = any(row["id"] == current_branch_id for row in facilities)
            available = any(row["state"] == "available" for row in facilities)
            state = "current" if is_current else (
                "visited" if reached_positions else "available" if available else "locked"
            )
            territories.append({
                "id": f"{sector['id']}-territory-{tier}", "tier": tier,
                "name": name, "state": state, "facilities": facilities,
            })
        map_sectors.append({
            "id": sector["id"], "name": sector["name"], "icon": sector["icon"],
            "territories": territories,
        })

    active_sector_id = branches[current_branch_id]["sector_id"] if current_branch_id else sector_id
    active_sector = next(row for row in map_sectors if row["id"] == active_sector_id)
    return {
        "revealed": revealed, "sector_id": sector_id,
        "active_sector_id": active_sector_id,
        "current_branch_id": current_branch_id,
        "next_branches": [branches[branch_id] for branch_id in sorted(next_ids) if branch_id in branches],
        "territory_count": 9, "sectors": map_sectors,
        "territories": active_sector["territories"],
        "unlock_requirement": {
            "branch_id": first_id, "facility_level": 8,
            "current_level": int(facility_levels.get(first_id, 0)) if first_id else 0,
            "message": "Улучшите первый завод до уровня 8, чтобы открыть карту территорий.",
        },
    }


__all__ = ["TERRITORY_NAMES", "build_progression_map"]
