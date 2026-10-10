"""Civilian corporation progression with frozen prices and finite NPC demand.

Public imports from the original catalogue remain available. Saved branch IDs
remain valid; cyclic old transitions are replaced with forward specialisations.
"""
from copy import deepcopy
from typing import Any
from .next_catalog import (
    CUSTOM_ITEMS, EXCLUDED_ITEMS, LEGACY_CORPORATIONS, LEGACY_RECIPES,
    NEXT_GAME_BASE_PRICES, SECTOR_NODES, START_BRANCH_IDS, LEGACY_NEXT_BRANCH_IDS,
)

from .next_catalog.validation import validate_tables

NPC_BUY_MARKUP = 1.20
NPC_SELL_MARKDOWN = 0.80
EPOCH_NAMES = {
    1: "Основная специализация", 2: "Промышленная переработка",
    3: "Ресурсная независимость", 4: "Развитие цепочек поставок",
    5: "Глубокая переработка", 6: "Интеграция отраслей",
    7: "Автоматизация", 8: "Передовые технологии", 9: "Системная экономика",
}

RECIPES = deepcopy(LEGACY_RECIPES)
# Former banking volumes were disproportionate to industrial output.
for _key, _quantity in {
    "ai_compute": 3, "atm_network": 20, "corporate_accounts": 18,
    "branch_network": 8, "clearing_house": 7, "asset_management": 7,
    "merchant_acquiring": 24,
}.items():
    _out, _, _inputs, _op = RECIPES[_key]
    RECIPES[_key] = (_out, _quantity, _inputs, _op)

NODE_METADATA = {}
NEXT_BRANCH_IDS: dict[str, tuple[str, ...]] = {}
_corporations = []
_legacy_rank = {row[0]: index for index, row in enumerate(
    row for *_, branches in LEGACY_CORPORATIONS for row in branches
)}
for _sector, _name, _icon, _description, _branches in LEGACY_CORPORATIONS:
    _legacy = list(_branches)
    _extra = SECTOR_NODES[_sector]
    _ids = [row[0] for row in _legacy]
    for _index, (_id, _label, _output, _future) in enumerate(_legacy):
        # Old nodes form a forward DAG inside their parent corporation. Existing
        # saved paths are identifiers, so they need no rewriting or reselection.
        _successors = [target for target in LEGACY_NEXT_BRANCH_IDS[_id]
                       if _legacy_rank[target] > _legacy_rank[_id]]
        _successors += _ids[_index + 1:_index + 3]
        _successors += [row[0] for row in _extra[:2]]
        NEXT_BRANCH_IDS[_id] = tuple(dict.fromkeys(_successors))
        NODE_METADATA[_id] = {
            "tier": 1 if _id in START_BRANCH_IDS[_sector] else 2,
            "facility_name": _label,
            "strategic_role": _output,
        }
    _all = list(_legacy)
    for _index, (_id, _label, _output, _quantity, _inputs, _stage) in enumerate(_extra):
        _tier = _stage + 1
        RECIPES[_id] = (_output, _quantity, _inputs, 25 + _tier * 10)
        _next_start = ((_index // 3) + 1) * 3
        _next_layer = _extra[_next_start:_next_start + 3]
        _position = _index % 3
        NEXT_BRANCH_IDS[_id] = tuple(
            _next_layer[position % len(_next_layer)][0]
            for position in (_position, _position + 1)
        ) if _next_layer else ()
        NODE_METADATA[_id] = {
            "tier": _tier, "facility_name": _label,
            "strategic_role": "Поставка: " + _output,
        }
        _all.append((_id, _label, _output, ()))
    # Three first-generation alternatives are reachable even from a saved last
    # legacy node; no existing player can be stranded in a former cycle.
    for _id in _ids:
        NEXT_BRANCH_IDS[_id] = (*NEXT_BRANCH_IDS[_id], _extra[2][0])
    _corporations.append((_sector, _name, _icon, _description, tuple(_all)))
CORPORATIONS = tuple(_corporations)


def get_next_game_items() -> dict[str, dict[str, Any]]:
    from backend.natbirzha.models.inventory import CANONICAL_ITEMS
    items = {
        key: {"name": row["name"], "unit": row["unit"],
              "base_price": NEXT_GAME_BASE_PRICES[key]}
        for key, row in CANONICAL_ITEMS.items() if key not in EXCLUDED_ITEMS
    }
    return {**items, **deepcopy(CUSTOM_ITEMS)}


def get_next_game_catalog() -> list[dict[str, Any]]:
    items = get_next_game_items()
    validate_tables(CORPORATIONS, RECIPES, NEXT_BRANCH_IDS, START_BRANCH_IDS, items)
    names = {row[0]: row[1] for *_, branches in CORPORATIONS for row in branches}
    consumers = {key: [] for key in items}
    for branch_id, (_, _, inputs, _) in RECIPES.items():
        for key in inputs:
            consumers[key].append(branch_id)
    catalog = []
    for sector_id, name, icon, description, branches in CORPORATIONS:
        rows = []
        for branch_id, branch_name, _outputs, _future in branches:
            output, quantity, inputs, operating_cost = RECIPES[branch_id]
            meta = NODE_METADATA[branch_id]
            tier = meta["tier"]
            input_cost = round(sum(items[key]["base_price"] * NPC_BUY_MARKUP * amount
                                   for key, amount in inputs.items()), 2)
            revenue = round(items[output]["base_price"] * NPC_SELL_MARKDOWN * quantity, 2)
            profit = round(revenue - input_cost - operating_cost, 2)
            is_start = branch_id in START_BRANCH_IDS[sector_id]
            build_cost = round(max(3000, profit * (24 + tier * 3)), -2)
            if is_start:
                build_cost = min(build_cost, 7000)
            cycle_seconds = 240 + tier * 60
            recipe = {
                "facility_name": meta["facility_name"], "build_cost": build_cost,
                "cycle_seconds": cycle_seconds, "output_item": output,
                "output_name": items[output]["name"], "output_unit": items[output]["unit"],
                "output_quantity": quantity, "net_output_quantity": quantity - inputs.get(output, 0),
                "inputs": dict(inputs),
                "input_items": [
                    {"item_id": key, "name": items[key]["name"], "unit": items[key]["unit"],
                     "quantity": amount, "npc_unit_cost": round(items[key]["base_price"] * NPC_BUY_MARKUP, 2),
                     "npc_total_cost": round(items[key]["base_price"] * NPC_BUY_MARKUP * amount, 2)}
                    for key, amount in inputs.items()
                ],
                "operating_cost": operating_cost,
                "economics": {
                    "npc_input_cost": input_cost, "npc_revenue": revenue,
                    "npc_profit": profit, "profit_per_hour": round(profit * 3600 / cycle_seconds, 2),
                    "payback_cycles": round(build_cost / profit, 2) if profit > 0 else None,
                    "price_policy": "frozen_2.0", "npc_buy_markup": NPC_BUY_MARKUP,
                    "npc_sell_markdown": NPC_SELL_MARKDOWN,
                    "demand_policy": "finite_treasury_cash_and_stock",
                },
            }
            rows.append({
                "id": branch_id, "name": branch_name, "outputs": items[output]["name"],
                "is_starting_branch": is_start,
                "future_choices": [names[key] for key in NEXT_BRANCH_IDS[branch_id]],
                "next_branch_ids": list(NEXT_BRANCH_IDS[branch_id]), "factory": recipe,
                "tier": tier, "epoch": EPOCH_NAMES[tier],
                "strategic_role": "Производство «" + items[output]["name"] + "» для цепочек поставок",
                "requirements": {"company_level": tier, "previous_factory_required": not is_start,
                                 "inputs": dict(inputs)},
                "demand_branch_ids": consumers[output],
                "terminal": not NEXT_BRANCH_IDS[branch_id],
            })
        catalog.append({"id": sector_id, "name": name, "icon": icon,
                        "description": description, "branches": rows})
    return catalog


def find_next_game_sector(sector_id: str) -> dict[str, Any] | None:
    return next((row for row in get_next_game_catalog() if row["id"] == sector_id), None)


def find_next_game_branch(branch_id: str) -> dict[str, Any] | None:
    return next((row for sector in get_next_game_catalog() for row in sector["branches"]
                 if row["id"] == branch_id), None)


__all__ = ["CORPORATIONS", "CUSTOM_ITEMS", "NEXT_BRANCH_IDS", "NEXT_GAME_BASE_PRICES",
           "RECIPES", "START_BRANCH_IDS", "find_next_game_branch", "find_next_game_sector",
           "get_next_game_catalog", "get_next_game_items"]
