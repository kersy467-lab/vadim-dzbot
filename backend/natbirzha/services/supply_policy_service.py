"""Opt-in purchase policies for resource businesses in NATBIRZHA 2.0."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.business_assets import NatBusinessSupplyPolicy
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, get_npc_sell_price
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.npc_service import NPCReserveService
from backend.natbirzha.services.market_procurement_service import MarketProcurementService


SUPPLY_POLICY_MODES = frozenset({"MANUAL", "AUTO_NPC", "AUTO_MARKET", "AUTO_MARKET_NPC"})


class SupplyPolicyService:

    @staticmethod
    def automation_policy_limit(level: int) -> int:
        """Number of resources the company can keep stocked automatically."""
        level = max(1, int(level))
        if level < 15:
            return 0
        if level < 25:
            return 1
        if level < 35:
            return 3
        if level < 50:
            return 6
        return 999

    @classmethod
    async def _active_company_policy_count(
        cls, session: AsyncSession, company_id: int, *, exclude_policy_id: int | None = None
    ) -> int:
        rows = (await session.execute(
            select(NatBusinessSupplyPolicy)
            .join(NatBusiness, NatBusiness.id == NatBusinessSupplyPolicy.business_id)
            .where(
                NatBusiness.company_id == company_id,
                NatBusinessSupplyPolicy.mode != "MANUAL",
            )
        )).scalars().all()
        return sum(1 for row in rows if exclude_policy_id is None or row.id != exclude_policy_id)

    @classmethod
    async def configure(
        cls,
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
            raise ValueError("Неизвестный режим автоснабжения")
        if min_hours_stock < 0 or target_hours_stock < min_hours_stock:
            raise ValueError("Целевой запас должен быть не меньше минимального")
        if max_unit_price is not None and max_unit_price <= 0:
            raise ValueError("Максимальная цена должна быть положительной")
        business = await session.scalar(
            select(NatBusiness).where(NatBusiness.id == business_id).with_for_update()
        )
        if business is None:
            raise ValueError("Предприятие не найдено")
        from backend.natbirzha.catalogs.businesses import get_business_spec
        spec = get_business_spec(business.business_type)
        if spec is None or item_id not in spec["inputs_per_hour"]:
            raise ValueError("Это предприятие не потребляет выбранный ресурс")
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == business.company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Компания не найдена")
        policy = await session.scalar(
            select(NatBusinessSupplyPolicy)
            .where(NatBusinessSupplyPolicy.business_id == business.id, NatBusinessSupplyPolicy.item_id == item_id)
            .with_for_update()
        )
        if normalized_mode != "MANUAL":
            limit = cls.automation_policy_limit(company.level)
            if limit <= 0:
                raise ValueError("Автоснабжение откроется на 15 уровне компании")
            used = await cls._active_company_policy_count(
                session, company.id, exclude_policy_id=policy.id if policy is not None else None
            )
            if used >= limit:
                raise ValueError(f"Лимит автоснабжения: {limit} ресурс(а/ов). Улучшайте компанию")
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

    @staticmethod
    async def _reserve_market_freight(
        session: AsyncSession, company_id: int
    ) -> NatInventory | None:
        """Lock one available logistics unit while an automatic market buy runs."""
        inventory = await session.scalar(
            select(NatInventory)
            .where(
                NatInventory.company_id == company_id,
                NatInventory.item_id == "logistics_capacity",
            )
            .with_for_update()
        )
        if inventory is None or float(inventory.available_quantity) < 1.0:
            return None
        inventory.reserved_quantity = round(float(inventory.reserved_quantity) + 1.0, 6)
        await session.flush()
        return inventory

    @staticmethod
    def _release_market_freight(inventory: NatInventory, *, consume: bool) -> None:
        inventory.reserved_quantity = round(
            max(0.0, float(inventory.reserved_quantity) - 1.0), 6
        )
        if consume:
            inventory.quantity = round(max(0.0, float(inventory.quantity) - 1.0), 6)

    @classmethod
    async def auto_procure(
        cls,
        session: AsyncSession,
        company: NatCompany,
        business: NatBusiness,
        spec: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Keep configured stock targets: player asks first, State reserve only as fallback."""
        policies = list((await session.execute(
            select(NatBusinessSupplyPolicy)
            .where(
                NatBusinessSupplyPolicy.business_id == business.id,
                NatBusinessSupplyPolicy.mode != "MANUAL",
            )
            .order_by(NatBusinessSupplyPolicy.item_id)
            .with_for_update()
        )).scalars().all())
        results: list[dict[str, Any]] = []
        rates = resource_business_rates(
            business, spec, upgrading=business.status == "UPGRADING"
        )
        for policy in policies:
            input_rate = float(spec["inputs_per_hour"].get(policy.item_id, 0.0)) * rates.input_multiplier
            if input_rate <= 0:
                continue
            inventory = await session.scalar(
                select(NatInventory)
                .where(NatInventory.company_id == company.id, NatInventory.item_id == policy.item_id)
                .with_for_update()
            )
            available = float(inventory.available_quantity) if inventory else 0.0
            minimum = input_rate * float(policy.min_hours_stock)
            target = input_rate * float(policy.target_hours_stock)
            if available + 1e-9 >= minimum:
                continue
            need = round(max(0.0, target - available), 6)
            if need <= 0:
                continue

            freight_inventory = None
            needs_freight = policy.mode in {"AUTO_MARKET", "AUTO_MARKET_NPC"}
            if needs_freight:
                freight_inventory = await cls._reserve_market_freight(session, company.id)
            if needs_freight and freight_inventory is None:
                market_result = {
                    "success": False,
                    "item_id": policy.item_id,
                    "requested": need,
                    "purchased": 0.0,
                    "reason": "logistics_capacity",
                }
            else:
                try:
                    market_result = await MarketProcurementService.buy_available(
                        session, company, policy.item_id, need,
                        max_unit_price=policy.max_unit_price,
                    )
                except Exception:
                    if freight_inventory is not None:
                        cls._release_market_freight(freight_inventory, consume=False)
                    raise
                if freight_inventory is not None:
                    filled = float(market_result.get("purchased", 0.0) or 0.0) > 1e-9
                    cls._release_market_freight(freight_inventory, consume=filled)
                    await session.flush()
            purchased = float(market_result.get("purchased", 0.0))
            results.append({"source": "MARKET", **market_result})
            remaining = round(max(0.0, need - purchased), 6)
            allow_reserve = policy.mode in {"AUTO_NPC", "AUTO_MARKET_NPC"} and policy.allow_state_reserve
            if remaining <= 0 or not allow_reserve:
                continue
            unit_price = get_npc_sell_price(policy.item_id)
            if policy.max_unit_price is not None and unit_price > float(policy.max_unit_price):
                results.append({"source": "STATE", "item_id": policy.item_id, "success": False, "reason": "price_limit"})
                continue
            try:
                npc_result = await NPCReserveService.execute_npc_trade(
                    session, company, policy.item_id, "BUY", remaining
                )
                results.append({"source": "STATE", **npc_result})
            except ValueError as exc:
                results.append({"source": "STATE", "item_id": policy.item_id, "success": False, "reason": str(exc)})
        return results


__all__ = ["SUPPLY_POLICY_MODES", "SupplyPolicyService"]
