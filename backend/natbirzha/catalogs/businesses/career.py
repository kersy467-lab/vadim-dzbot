"""Helpers for compact 50-stage industry career catalogs."""

from typing import Any, Iterable, Mapping, Sequence

from backend.natbirzha.models.inventory import get_npc_buy_price, get_npc_sell_price

from .schema import business_spec


_TARGET_OPEN_ROI_HOURS = (10, 14, 20, 28, 38, 50, 64, 80, 98, 118, 140, 164)


def _target_open_roi_hours(order: int) -> float:
    """Target state-reserve break-even horizon for a fresh career enterprise.

    Early businesses repay quickly enough to teach the loop. Late businesses
    take days, so unlocking a new strategic complex remains a meaningful goal.
    Player-to-player sourcing/sales can beat these conservative NPC economics.
    """
    index = min(len(_TARGET_OPEN_ROI_HOURS) - 1, max(0, int(order) - 1))
    return float(_TARGET_OPEN_ROI_HOURS[index])


def _calibrate_outputs(
    outputs: Mapping[str, float],
    inputs: Mapping[str, float],
    *,
    open_cost: float,
    maintenance_per_hour: float,
    order: int,
    opening_resources: Mapping[str, float],
) -> tuple[dict[str, float], float, float]:
    """Scale declared physical output to a playable NPC fallback economy.

    The State intentionally buys low and sells high. Without one common
    calibration layer, recipes expressed in different physical units (barrels,
    litres, tonnes, pieces) easily become accidental money printers or permanent
    loss-makers. We preserve each recipe's relative output mix while targeting
    a conservative payback horizon for the enterprise's place in the career.
    """
    normalized = {str(item_id): max(0.0, float(quantity)) for item_id, quantity in outputs.items()}
    current_revenue = sum(quantity * get_npc_buy_price(item_id) for item_id, quantity in normalized.items())
    if current_revenue <= 0:
        return normalized, 1.0, _target_open_roi_hours(order)

    input_cost = sum(
        max(0.0, float(quantity)) * get_npc_sell_price(item_id)
        for item_id, quantity in inputs.items()
    )
    construction_cost = sum(
        max(0.0, float(quantity)) * get_npc_sell_price(item_id)
        for item_id, quantity in opening_resources.items()
    )
    roi_hours = _target_open_roi_hours(order)
    target_profit = max(150.0, (float(open_cost) + construction_cost) / roi_hours)
    target_revenue = input_cost + max(0.0, float(maintenance_per_hour)) + target_profit
    scale = max(0.25, min(1000.0, target_revenue / current_revenue))
    calibrated = {item_id: round(quantity * scale, 4) for item_id, quantity in normalized.items()}
    return calibrated, round(scale, 6), roi_hours


MILESTONE_STAGES = (10, 20, 30, 40, 50)
_MILESTONE_OUTPUT_MULTIPLIERS = (1.13, 1.195, 1.26, 1.325, 1.39)


_EVENT_RESOURCE_PROFILES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("столов", "питани", "смена", "лагер", "посёл"), ("grain", "milk", "lumber")),
    (("дренаж", "водо", "насос", "иррига", "очист", "фильтр"), ("steel", "energy", "basic_chem")),
    (("самосвал", "буров", "техник", "гараж", "механиз"), ("steel", "fuel_diesel", "machinery")),
    (("автомат", "цифров", "робот", "датчик", "интеллект"), ("electronics", "sensors", "automation_systems")),
    (("подстанц", "электр", "генератор", "турбин", "инвертор"), ("copper", "steel", "electronics")),
    (("хранилищ", "склад", "резервуар", "элеватор"), ("steel", "concrete", "lumber")),
    (("лаборатор", "реагент", "химичес", "агрохим"), ("basic_chem", "clean_water", "electronics")),
    (("железнодорож", "терминал", "порт", "логист", "транспорт"), ("steel", "fuel_diesel", "logistics_capacity")),
    (("вентиляц", "подъёмник", "укреп", "тоннел"), ("steel", "machinery", "energy")),
    (("переработ", "обогат", "сепарац", "сортиров", "дробил", "линия"), ("machinery", "energy", "electronics")),
    (("охран", "защищ", "радиац"), ("steel", "electronics", "basic_chem")),
    (("тепли", "коров", "корм", "птиц", "ветерин"), ("lumber", "water", "food")),
)

_EVENT_BASE_AMOUNTS: dict[str, float] = {
    "grain": 80, "milk": 40, "lumber": 30, "steel": 40, "energy": 100,
    "water": 100, "basic_chem": 12, "fuel_diesel": 30, "machinery": 10,
    "electronics": 10, "sensors": 8, "automation_systems": 4, "copper": 20,
    "concrete": 35, "clean_water": 60, "logistics_capacity": 12, "food": 50,
}


def _event_resources(
    title: str, fallback: Sequence[str], *, factor: float, index: int
) -> dict[str, float]:
    lowered = title.casefold()
    items: Sequence[str] = fallback
    for keywords, profile in _EVENT_RESOURCE_PROFILES:
        if any(keyword in lowered for keyword in keywords):
            items = profile
            break
    count = min(len(items), 2 + index // 2)
    return {
        item_id: round(_EVENT_BASE_AMOUNTS.get(item_id, 20.0 + offset * 8.0) * factor, 2)
        for offset, item_id in enumerate(items[:count])
    }


def milestone_chain(
    titles: Sequence[str],
    *,
    scale: float,
    resource_pool: Sequence[str],
    descriptions: Sequence[str] | None = None,
) -> dict[int, dict[str, Any]]:
    """Build five deterministic, increasingly expensive story projects."""
    if len(titles) != 5:
        raise ValueError("A career business requires exactly five milestone titles")
    result: dict[int, dict[str, Any]] = {}
    descriptions = descriptions or ()
    for index, stage in enumerate(MILESTONE_STAGES):
        factor = 0.5 * max(1.0, scale) * (index + 1) ** 1.55
        resources = _event_resources(
            titles[index], resource_pool, factor=factor, index=index
        )
        result[stage] = {
            "label": titles[index],
            "description": descriptions[index] if index < len(descriptions) else titles[index],
            "resources": resources,
            "cash_multiplier": round(1.25 + index * 0.35, 2),
            "duration_multiplier": round(1.0 + index * 0.45, 2),
            "output_multiplier": _MILESTONE_OUTPUT_MULTIPLIERS[index],
            "input_multiplier": round(0.99 - index * 0.0125, 3),
        }
    return result


def _default_open_resources(order: int) -> dict[str, float]:
    """Cross-industry construction package for opening non-starter enterprises."""
    order = max(1, int(order))
    if order <= 1:
        return {}
    factor = float(order) ** 1.28
    if order <= 3:
        profile = (("steel", 5.0), ("lumber", 3.0))
    elif order <= 6:
        profile = (("steel", 7.0), ("concrete", 5.0), ("copper", 2.5))
    elif order <= 9:
        profile = (("steel", 9.0), ("machinery", 1.7), ("electronics", 1.2))
    else:
        profile = (("steel", 11.0), ("electronics", 2.0), ("automation_systems", 0.7), ("basic_chem", 1.4))
    return {item_id: round(base * factor, 2) for item_id, base in profile}


def career_business(
    *,
    business_id: str,
    name: str,
    icon: str,
    specialization: str,
    order: int,
    open_cost: float,
    level_required: int,
    inputs: Mapping[str, float],
    outputs: Mapping[str, float],
    milestones: Sequence[str],
    milestone_resources: Sequence[str],
    description: str,
    prerequisites: Mapping[str, int] | None = None,
    territory_required: int = 0,
    open_resources: Mapping[str, float] | None = None,
    slot_weight: int = 1,
    mechanic: str = "resource_production",
    base_income_per_hour: float = 0.0,
    tags: Iterable[str] = (),
    starter: bool = False,
    unique: bool = False,
) -> dict[str, Any]:
    """Create one standard long-form enterprise with 50 progression stages."""
    tier = min(5, 1 + max(0, order - 1) // 2)
    maintenance_per_hour = max(8.0, open_cost * 0.0007)
    opening_resources = (
        dict(open_resources)
        if open_resources is not None
        else _default_open_resources(order)
    )
    calibrated_outputs, output_balance_factor, target_roi_hours = _calibrate_outputs(
        outputs, inputs,
        open_cost=open_cost,
        maintenance_per_hour=maintenance_per_hour,
        order=order,
        opening_resources=opening_resources,
    )
    spec = business_spec(
        business_id=business_id,
        name=name,
        icon=icon,
        description=description,
        tier=tier,
        mechanic=mechanic,
        specialization=specialization,
        max_stage=50,
        open_cost=open_cost,
        base_income_per_hour=base_income_per_hour,
        base_maintenance_per_hour=maintenance_per_hour,
        income_growth=1.10,
        input_growth=1.03,
        output_growth=1.10,
        upgrade_cost_growth=1.12,
        upgrade_time_curve="career",
        inputs_per_hour=inputs,
        outputs_per_hour=calibrated_outputs,
        milestones=milestone_chain(
            milestones,
            scale=max(1.0, order * 0.65),
            resource_pool=milestone_resources,
        ),
        slot_weight=slot_weight,
        upgrade_downtime_mult=1.0,
        company_level_required=level_required,
        prerequisites=prerequisites,
        territory_required=territory_required,
        open_resources=opening_resources,
        industry_order=order,
        starter=starter,
        unique=unique,
        tags=tuple(tags),
    )
    spec["output_balance_factor"] = output_balance_factor
    spec["target_open_roi_hours"] = target_roi_hours
    spec["upgrade_cost_base_multiplier"] = 0.05
    return spec
