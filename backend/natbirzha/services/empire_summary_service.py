"""Server-owned read model for the NATBIRZHA 2.0 idle empire screen."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, nat_settings, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.business_assets import NatBusinessSupplyPolicy
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, get_npc_buy_price, get_npc_sell_price
from backend.natbirzha.services.business_rates import cash_business_rates, resource_business_rates
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.supply_policy_service import SupplyPolicyService
from backend.natbirzha.services.business_asset_service import BusinessAssetService
from backend.natbirzha.services.progression_service import progress_snapshot


class EmpireSummaryService:
    """Build presentation data without trusting the client with game formulas."""

    @staticmethod
    def _resource_value(entries: dict[str, float], *, selling: bool) -> float:
        price = get_npc_buy_price if selling else get_npc_sell_price
        total = 0.0
        for item_id, quantity in entries.items():
            try:
                total += float(quantity) * price(item_id)
            except ValueError:
                continue
        return total

    @classmethod
    def _serialize_business(
        cls,
        business: NatBusiness,
        inventory: dict[str, float],
        supply_policies: dict[str, dict[str, Any]] | None = None,
        assets: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        spec = get_business_spec(business.business_type)
        if spec is None:
            return {
                "id": business.id,
                "name": "Неизвестное предприятие",
                "business_type": business.business_type,
                "stage": business.stage,
                "status": business.status,
                "catalog_missing": True,
            }

        is_resource = spec["mechanic"] == "resource_production"
        next_upgrade = None
        upgradeable_statuses = {
            "ACTIVE", "PAUSED_MANUAL", "PAUSED_SUPPLY",
            "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
        }
        if business.stage < int(spec["max_stage"]) and business.status in upgradeable_statuses:
            next_upgrade = BusinessService.upgrade_quote(spec, business.stage)
        contract_expired = bool((business.metadata_json or {}).get("contract_expired"))
        if contract_expired:
            next_upgrade = None

        if is_resource:
            rates = resource_business_rates(
                business, spec, upgrading=business.status == "UPGRADING"
            )
            inputs = {
                item_id: round(float(value) * rates.input_multiplier, 4)
                for item_id, value in spec["inputs_per_hour"].items()
            }
            outputs = {
                item_id: round(float(value) * rates.output_multiplier, 4)
                for item_id, value in spec["outputs_per_hour"].items()
            }
            autonomy_values = [
                float(inventory.get(item_id, 0.0)) / rate
                for item_id, rate in inputs.items()
                if rate > 0
            ]
            autonomy = min(autonomy_values) if autonomy_values else None
            stock_hours = {
                item_id: round(float(inventory.get(item_id, 0.0)) / rate, 2)
                for item_id, rate in inputs.items() if rate > 0
            }
            revenue = cls._resource_value(outputs, selling=True)
            input_cost = cls._resource_value(inputs, selling=False)
            maintenance = rates.maintenance_per_hour
            estimated_profit = revenue - input_cost - maintenance
            sale_mode = str((business.metadata_json or {}).get("sale_mode", "NPC")).upper()
            if sale_mode not in {"NPC", "HOLD"}:
                sale_mode = "NPC"
            gross = revenue if sale_mode == "NPC" else 0.0
            net = gross - maintenance
        else:
            sale_mode = None
            cash_rates = cash_business_rates(
                business, spec, upgrading=business.status == "UPGRADING"
            )
            inputs = spec["inputs_per_hour"]
            outputs = spec["outputs_per_hour"]
            autonomy = None
            stock_hours = {}
            revenue = cash_rates.gross_per_hour
            input_cost = 0.0
            maintenance = cash_rates.maintenance_per_hour
            estimated_profit = cash_rates.net_per_hour
            gross = cash_rates.gross_per_hour
            net = cash_rates.net_per_hour

        tick_minutes = max(1, int(nat_settings.TYCOON_V2_RESOURCE_TICK_MINUTES))
        tick_factor = tick_minutes / 60.0
        inputs_per_tick = {item_id: round(value * tick_factor, 4) for item_id, value in inputs.items()}
        outputs_per_tick = {item_id: round(value * tick_factor, 4) for item_id, value in outputs.items()}
        policies = supply_policies or {}
        supply = {
            item_id: policies.get(item_id, {
                "item_id": item_id,
                "mode": "MANUAL",
                "min_hours_stock": 0.0,
                "target_hours_stock": 0.0,
                "max_unit_price": None,
                "allow_state_reserve": False,
            })
            for item_id in inputs
        }
        milestone = next_upgrade.get("milestone") if next_upgrade else None
        return {
            "id": business.id,
            "name": business.custom_name or spec["name"],
            "catalog_name": spec["name"],
            "description": spec.get("description", ""),
            "icon": spec.get("icon", "🏢"),
            "business_type": business.business_type,
            "specialization": business.specialization,
            "mechanic": spec["mechanic"],
            "stage": business.stage,
            "max_stage": spec["max_stage"],
            "status": business.status,
            "contract_expired": contract_expired,
            "contract_license": (business.metadata_json or {}).get("contract_license"),
            "slot_weight": business.slot_weight,
            "gross_per_hour": round(gross, 2),
            "maintenance_per_hour": round(maintenance, 2),
            "net_per_hour": round(net, 2),
            "estimated_revenue_per_hour": round(revenue, 2),
            "estimated_input_cost_per_hour": round(input_cost, 2),
            "estimated_profit_per_hour": round(estimated_profit, 2),
            "sale_mode": sale_mode,
            "autonomy_hours": round(autonomy, 2) if autonomy is not None else None,
            "stock_hours_by_item": stock_hours,
            "resource_tick_minutes": tick_minutes,
            "inputs_per_hour": inputs,
            "outputs_per_hour": outputs,
            "inputs_per_tick": inputs_per_tick,
            "outputs_per_tick": outputs_per_tick,
            "supply_policies": supply,
            "upgrade_ready_at": business.upgrade_ready_at,
            "next_upgrade": next_upgrade,
            "next_milestone": milestone,
            "assets": assets or {},
        }

    @classmethod
    async def build(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        company = await session.scalar(select(NatCompany).where(NatCompany.id == company_id))
        if company is None:
            raise ValueError("Компания не найдена")
        businesses = list((await session.execute(
            select(NatBusiness)
            .where(NatBusiness.company_id == company.id)
            .order_by(NatBusiness.created_at, NatBusiness.id)
        )).scalars().all())
        inventory_rows = (await session.execute(
            select(NatInventory).where(NatInventory.company_id == company.id)
        )).scalars().all()
        inventory = {row.item_id: float(row.available_quantity) for row in inventory_rows}
        visible_businesses = [
            business for business in businesses
            if not (get_business_spec(business.business_type) or {}).get("legacy_hidden", False)
        ]
        ids = [business.id for business in visible_businesses]
        policy_rows = [] if not ids else list((await session.execute(
            select(NatBusinessSupplyPolicy).where(NatBusinessSupplyPolicy.business_id.in_(ids))
        )).scalars().all())
        policies_by_business: dict[int, dict[str, dict[str, Any]]] = {}
        for policy in policy_rows:
            policies_by_business.setdefault(policy.business_id, {})[policy.item_id] = {
                "item_id": policy.item_id,
                "mode": policy.mode,
                "min_hours_stock": policy.min_hours_stock,
                "target_hours_stock": policy.target_hours_stock,
                "max_unit_price": policy.max_unit_price,
                "allow_state_reserve": policy.allow_state_reserve,
            }
        active_auto_policies = sum(1 for policy in policy_rows if policy.mode != "MANUAL")
        auto_policy_limit = SupplyPolicyService.automation_policy_limit(company.level)
        assets_by_business = await BusinessAssetService.snapshot_for_businesses(session, visible_businesses)
        serialized = [
            cls._serialize_business(
                business, inventory, policies_by_business.get(business.id), assets_by_business.get(business.id)
            )
            for business in visible_businesses
        ]
        used_slots = sum(
            int(business.slot_weight) for business in visible_businesses
            if business.status != "BANKRUPT"
        )
        active_projects = sum(
            1 for business in visible_businesses
            if business.status == "UPGRADING" and BusinessService._is_milestone_upgrade(business)
        )
        gross = sum(item.get("gross_per_hour", 0.0) for item in serialized)
        expenses = sum(item.get("maintenance_per_hour", 0.0) for item in serialized)
        estimated_profit = sum(item.get("estimated_profit_per_hour", 0.0) for item in serialized)
        return {
            "company_id": company.id,
            "specialization": company.specialization,
            "level": company.level,
            "progression": {
                **progress_snapshot(company),
                "work_xp_per_hour": max(1, int(nat_settings.TYCOON_V2_WORK_XP_PER_HOUR)),
            },
            "territory_tiles": company.territory_tiles,
            "cash": round(float(company.cash), 2),
            "income_per_hour": round(gross, 2),
            "expenses_per_hour": round(expenses, 2),
            "net_cash_per_hour": round(gross - expenses, 2),
            "estimated_profit_per_hour": round(estimated_profit, 2),
            "slots": BusinessService.business_slot_limits(
                level=company.level, territory_tiles=company.territory_tiles, used=used_slots
            ),
            "project_slots": BusinessService.project_slot_limits(
                level=company.level, active=active_projects
            ),
            "offline_cap_hours": __import__(
                "backend.natbirzha.services.idle_economy_service",
                fromlist=["IdleEconomyService"],
            ).IdleEconomyService.offline_cap_hours(company),
            "resource_tick_minutes": max(1, int(nat_settings.TYCOON_V2_RESOURCE_TICK_MINUTES)),
            "supply_automation": {
                "used": active_auto_policies,
                "max": auto_policy_limit,
                "unlocked": auto_policy_limit > 0,
                "next_unlock_level": 15 if company.level < 15 else (25 if company.level < 25 else (35 if company.level < 35 else (50 if company.level < 50 else None))),
            },
            "businesses": serialized,
            "generated_at": normalize_dt(now or get_game_now()),
        }


__all__ = ["EmpireSummaryService"]
