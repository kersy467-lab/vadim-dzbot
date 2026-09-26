"""Reproducible catalog stress test; no database or live accounts are touched."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.army_service import RECRUITMENT_CATALOG
from backend.natbirzha.services.business_asset_catalog import PROJECT_CATALOG

ROI_BASIS = (
    "Theoretical only: assumes all output can be sold at canonical reference prices, "
    "all required inputs are available, and output inventory never blocks production."
)
NPC_PROFIT_BASIS = (
    "Unlimited NPC spread stress scenario: applies the configured NPC buy/sell price multipliers "
    "to all modeled volume and ignores NPC_DAILY_BUYBACK_CASH_LIMIT; not a realized-profit forecast."
)
INVENTORY_FILL_HORIZONS = (24, 48, 72, 168)


def value(items, multiplier=1.0):
    return sum(float(q) * CANONICAL_ITEMS[k]["base_price"] * multiplier for k, q in items.items())


def output_inventory_projection(outputs_per_hour, minimum_cap, horizon_hours):
    """Estimate fill time with the V2 per-company offline-output allowance."""
    fill_hours = {
        item: (float(minimum_cap) + float(quantity) * float(horizon_hours)) / float(quantity)
        for item, quantity in outputs_per_hour.items()
        if float(quantity) > 0
    }
    if not fill_hours:
        return {}, None, None, False
    first_item, first_hours = min(fill_hours.items(), key=lambda pair: (pair[1], pair[0]))
    return fill_hours, first_item, first_hours, first_hours <= float(horizon_hours)


def evaluate():
    rows = []
    flows = defaultdict(lambda: {"supply": defaultdict(float), "demand": defaultdict(float)})
    inventory_cap = float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM)
    inventory_horizon = float(nat_settings.TYCOON_V2_OFFLINE_CASH_CAP_HOURS)
    for spec in CAREER_BUSINESSES.values():
        capital = spec["open_cost"] + value(spec["open_resources"])
        previous_profit = None
        for stage in range(1, spec["max_stage"] + 1):
            upgrade_capital = 0.0
            if stage > 1:
                quote = BusinessService.upgrade_quote(spec, stage - 1)
                upgrade_capital = quote["cost"] + value((quote["milestone"] or {}).get("resources", {}))
                capital += upgrade_capital
            business = NatBusiness(stage=stage, health=100, efficiency=1,
                base_maintenance_per_hour=spec["base_maintenance_per_hour"], metadata_json={})
            rates = resource_business_rates(business, spec, upgrading=False)
            inputs = {k: q * rates.input_multiplier for k, q in spec["inputs_per_hour"].items()}
            outputs = {k: q * rates.output_multiplier for k, q in spec["outputs_per_hour"].items()}
            revenue, costs = value(outputs), value(inputs)
            fill_hours, first_fill_item, first_fill_hours, fills_within_horizon = output_inventory_projection(
                outputs, inventory_cap, inventory_horizon
            )
            profit = revenue - costs - rates.maintenance_per_hour
            net = profit * (1 - nat_settings.TAX_RATE)
            npc_profit = revenue * nat_settings.NPC_BUY_FLOOR_MULT - costs * nat_settings.NPC_SELL_CAP_MULT - rates.maintenance_per_hour
            utility_stress = sum(q * CANONICAL_ITEMS[k]["base_price"] * .5 for k, q in inputs.items() if k in {"energy", "water"})
            incremental = None if previous_profit is None else net - previous_profit
            rows.append({"business": spec["id"], "industry": spec["specialization"],
                "order": spec["industry_order"], "stage": stage, "capital": round(capital, 2),
                "revenue": round(revenue, 4), "inputs": round(costs, 4),
                "maintenance": round(rates.maintenance_per_hour, 4), "profit_after_tax": round(net, 4),
                "payback_hours": round(capital / net, 4) if net > 0 else None,
                "roi_basis": ROI_BASIS,
                "outputs_per_hour_by_item": json.dumps(outputs, ensure_ascii=False, sort_keys=True),
                "output_cap_fill_hours_by_item": json.dumps(fill_hours, ensure_ascii=False, sort_keys=True),
                "first_output_to_fill_inventory_cap": first_fill_item,
                "hours_to_fill_first_output_inventory_cap": round(first_fill_hours, 8) if first_fill_hours is not None else None,
                "fills_output_inventory_cap_within_base_offline_horizon": fills_within_horizon,
                "npc_profit": round(npc_profit, 4), "utility_stress_profit": round(profit - utility_stress, 4),
                "npc_profit_basis": NPC_PROFIT_BASIS,
                "upgrade_payback_hours": round(upgrade_capital / incremental, 4) if incremental and incremental > 0 else None,
                "input_output_scale_ratio": round(rates.input_multiplier / rates.output_multiplier, 6)})
            previous_profit = net
            if stage in (1, 10, 25, 50):
                for k, q in inputs.items(): flows[stage]["demand"][k] += q
                for k, q in outputs.items(): flows[stage]["supply"][k] += q
    summary = {"businesses": len(CAREER_BUSINESSES), "stages_checked": len(rows),
        "loss_making_market": sum(r["profit_after_tax"] <= 0 for r in rows),
        "loss_making_npc": sum(r["npc_profit"] <= 0 for r in rows),
        "loss_making_utility_stress": sum(r["utility_stress_profit"] <= 0 for r in rows),
        "npc_loss_scenario": {
            "loss_making_stage_rows": sum(r["npc_profit"] <= 0 for r in rows),
            "basis": NPC_PROFIT_BASIS,
        },
        "unprofitable_upgrades": sum(r["stage"] > 1 and r["upgrade_payback_hours"] is None for r in rows),
        "roi_basis": ROI_BASIS,
        "stages": {}}
    for stage, flow in flows.items():
        group = defaultdict(list)
        for row in rows:
            if row["stage"] == stage:
                group[row["industry"]].append(row["profit_after_tax"] / row["capital"] * 100)
        summary["stages"][stage] = {
            "industry_median_return_pct": {k: round(median(v), 4) for k, v in group.items()},
            "demand_supply_ratio": {k: round(flow["demand"][k] / v, 5) for k, v in flow["supply"].items() if v > 0}}
    produced = {k for s in CAREER_BUSINESSES.values() for k in s["outputs_per_hour"]}
    recurring_consumed = {k for s in CAREER_BUSINESSES.values() for k in s["inputs_per_hour"]}
    catalog_consumed = set(recurring_consumed)
    catalog_consumed.update(k for s in CAREER_BUSINESSES.values() for k in s["open_resources"])
    catalog_consumed.update(
        k for s in CAREER_BUSINESSES.values()
        for m in s["milestones"].values()
        for k in m.get("resources", {})
    )
    project_and_army_consumed = {
        k for s in PROJECT_CATALOG.values() for k in s["inputs"]
    }
    project_and_army_consumed.update(
        k for s in RECRUITMENT_CATALOG.values() for k in s["items"]
    )
    gameplay_consumed = catalog_consumed | project_and_army_consumed
    summary["flow_basis"] = (
        "Recurring recipe demand divided by recipe output for one copy of every career business at the same stage. "
        "One-time openings, upgrades, projects and military purchases are listed separately and are not treated as hourly demand."
    )
    summary["no_recurring_business_demand"] = sorted(produced - recurring_consumed)
    summary["no_industrial_consumer"] = sorted(produced - catalog_consumed)
    summary["no_gameplay_consumer"] = sorted(produced - gameplay_consumed)
    summary["project_or_army_only_sinks"] = sorted(
        (produced & project_and_army_consumed) - catalog_consumed
    )
    summary["missing_producer"] = sorted(catalog_consumed - produced)
    cap_stages = {}
    for stage in sorted({row["stage"] for row in rows}):
        stage_rows = [row for row in rows if row["stage"] == stage]
        output_streams = []
        businesses_filling = 0
        fills_by_horizon = {
            str(horizon): {"businesses_filling_any_output": 0, "output_items_filling_cap": 0}
            for horizon in INVENTORY_FILL_HORIZONS
        }
        for row in stage_rows:
            outputs = json.loads(row["outputs_per_hour_by_item"])
            for horizon in INVENTORY_FILL_HORIZONS:
                fill_hours, _, _, _ = output_inventory_projection(outputs, inventory_cap, horizon)
                filled_items = [item for item, hours in fill_hours.items() if hours <= horizon]
                fills_by_horizon[str(horizon)]["output_items_filling_cap"] += len(filled_items)
                if filled_items:
                    fills_by_horizon[str(horizon)]["businesses_filling_any_output"] += 1
            horizon_fill_hours, _, _, _ = output_inventory_projection(
                outputs, inventory_cap, inventory_horizon
            )
            output_streams.extend(
                (hours, row["business"], item)
                for item, hours in horizon_fill_hours.items()
            )
            first_fill = min(horizon_fill_hours.values(), default=None)
            if first_fill is not None and first_fill <= inventory_horizon:
                businesses_filling += 1
        fastest = min(output_streams) if output_streams else None
        cap_stages[str(stage)] = {
            "businesses_total": len(stage_rows),
            "businesses_filling_any_output": businesses_filling,
            "output_items_filling_cap": fills_by_horizon[str(int(inventory_horizon))]["output_items_filling_cap"],
            "fill_by_horizon_hours": fills_by_horizon,
            "fastest_fill": ({
                "hours": round(fastest[0], 8),
                "business": fastest[1],
                "item": fastest[2],
            } if fastest else None),
        }
    summary["output_inventory_cap"] = {
        "units_per_item": int(inventory_cap) if inventory_cap.is_integer() else inventory_cap,
        "horizon_hours": int(inventory_horizon) if inventory_horizon.is_integer() else inventory_horizon,
        "policy": "configured minimum per item plus this company's total live V2 output for its offline settlement horizon",
        "horizon_basis": "24-hour configured base; idle settlement extends this at company level 20+ (48h), 40+ (72h), and 60+ (168h).",
        "assumption": "Each business is measured alone from zero stock; capacity uses configured minimum plus that business's full gross output over the tested offline horizon. Existing stock, same-company producers, sales, and consumption are excluded.",
        "stages": cap_stages,
    }
    return rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Output prefix for .json and .csv")
    args = parser.parse_args()
    rows, summary = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: v for k, v in summary.items() if k != "stages"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
