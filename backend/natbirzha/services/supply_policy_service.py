"""Opt-in purchase policies for resource businesses in NATBIRZHA 2.0."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.business_assets import NatBusinessSupplyPolicy
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, get_npc_sell_price
from backend.natbirzha.services.npc_service import NPCReserveService


SUPPLY_POLICY_MODES = frozenset({"MANUAL", "AUTO_NPC"})


class SupplyPolicyService:
    @staticmethod
    async def configure(
        session: AsyncSession,
        business_id: int,
        item_id: str,
        *,
        mode: str,
        min_hours_stock: float,
        target_hours_stock: float,
        max_unit_price: float | None,
        allow_state_reserve: bool,
    ) -> dict[str, Any]:
        normalized_mode = (mode or "").strip().upper()
        if normalized_mode not in SUPPLY_POLICY_MODES:
            raise ValueError("Unknown supply policy mode")
        if min_hours_stock < 0 or target_hours_stock < min_hours_stock:
            raise ValueError("Supply target must be at least the minimum stock")
        if max_unit_price is not None and max_unit_price <= 0:
            raise ValueError("Maximum unit price must be positive")
        business = await session.scalar(
            select(NatBusiness).where(NatBusiness.id == business_id).with_for_update()
        )
        if business is None:
            raise ValueError("Business not found")
        from backend.natbirzha.catalogs.businesses import get_business_spec
        spec = get_business_spec(business.business_type)
        if spec is None or item_id not in spec["inputs_per_hour"]:
            raise ValueError("This business does not consume the selected resource")
        policy = await session.scalar(
            select(NatBusinessSupplyPolicy)
            .where(NatBusinessSupplyPolicy.business_id == business.id, NatBusinessSupplyPolicy.item_id == item_id)
            .with_for_update()
        )
        if policy is None:
            policy = NatBusinessSupplyPolicy(business_id=business.id, item_id=item_id)
            session.add(policy)
        policy.mode = normalized_mode
        policy.min_hours_stock = round(float(min_hours_stock), 2)
        policy.target_hours_stock = round(float(target_hours_stock), 2)
        policy.max_unit_price = round(float(max_unit_price), 2) if max_unit_price is not None else None
        policy.allow_state_reserve = bool(allow_state_reserve)
        await session.flush()
        return SupplyPolicyService.serialize(policy)

    @staticmethod
    def serialize(policy: NatBusinessSupplyPolicy) -> dict[str, Any]:
        return {
            "item_id": policy.item_id,
            "mode": policy.mode,
            "min_hours_stock": policy.min_hours_stock,
            "target_hours_stock": policy.target_hours_stock,
            "max_unit_price": policy.max_unit_price,
            "allow_state_reserve": policy.allow_state_reserve,
        }

    @classmethod
    async def auto_procure(
        cls,
        session: AsyncSession,
        company: NatCompany,
        business: NatBusiness,
        spec: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fill only explicit AUTO_NPC policies up to their stock target."""
        policies = list((await session.execute(
            select(NatBusinessSupplyPolicy)
            .where(NatBusinessSupplyPolicy.business_id == business.id, NatBusinessSupplyPolicy.mode == "AUTO_NPC")
            .order_by(NatBusinessSupplyPolicy.item_id)
            .with_for_update()
        )).scalars().all())
        results: list[dict[str, Any]] = []
        for policy in policies:
            input_rate = float(spec["inputs_per_hour"].get(policy.item_id, 0.0))
            if input_rate <= 0 or not policy.allow_state_reserve:
                continue
            unit_price = get_npc_sell_price(policy.item_id)
            if policy.max_unit_price is not None and unit_price > float(policy.max_unit_price):
                results.append({"item_id": policy.item_id, "success": False, "reason": "price_limit"})
                continue
            inventory = await session.scalar(
                select(NatInventory)
                .where(NatInventory.company_id == company.id, NatInventory.item_id == policy.item_id)
                .with_for_update()
            )
            available = float(inventory.available_quantity) if inventory else 0.0
            min_quantity = input_rate * float(policy.min_hours_stock)
            target_quantity = input_rate * float(policy.target_hours_stock)
            if available + 1e-9 >= min_quantity:
                continue
            quantity = round(max(0.0, target_quantity - available), 6)
            if quantity <= 0:
                continue
            result = await NPCReserveService.execute_npc_trade(
                session, company, policy.item_id, "BUY", quantity
            )
            results.append(result)
        return results


__all__ = ["SUPPLY_POLICY_MODES", "SupplyPolicyService"]
