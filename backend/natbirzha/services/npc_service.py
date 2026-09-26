from math import isfinite
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, get_game_today, nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import (
    CANONICAL_ITEMS,
    NatInventory,
    get_item_base_price,
    get_npc_buy_price,
    get_npc_sell_price,
)
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.services.npc_quota_service import NPCQuotaMixin
from backend.natbirzha.services.progression_service import apply_xp
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.inventory_capacity_service import InventoryCapacityService


class NPCReserveService(NPCQuotaMixin):
    """State reserve with finite per-item daily player buyback liquidity."""

    @staticmethod
    def get_npc_quote(item_id: str) -> Dict[str, Any]:
        if item_id not in CANONICAL_ITEMS:
            raise ValueError(f"Unknown item: {item_id}")
        # Lazy import to avoid circular dependency
        from backend.natbirzha.services.sabotage_service import SabotageService

        base = get_item_base_price(item_id)  # already includes crisis multiplier
        buy_floor = get_npc_buy_price(item_id)  # derived from base, also crisis-adjusted
        sell_cap = get_npc_sell_price(item_id)  # same

        # Informational only — actual prices already include crisis via get_item_base_price
        crisis_mult = SabotageService.get_resource_multiplier_sync(item_id)

        return {
            "item_id": item_id,
            "name": CANONICAL_ITEMS[item_id]["name"],
            "unit": CANONICAL_ITEMS[item_id]["unit"],
            "base_price": base,
            "npc_buy_price": buy_floor,
            "npc_sell_price": sell_cap,
            "spread_pct": round(((sell_cap - buy_floor) / base) * 100, 1) if base else 0.0,
            "crisis_multiplier": crisis_mult,
        }



    @staticmethod
    async def _daily_financials(session: AsyncSession, company_id: int) -> NatDailyFinancials:
        today = get_game_today()
        result = await session.execute(
            select(NatDailyFinancials).where(
                NatDailyFinancials.company_id == company_id,
                NatDailyFinancials.calendar_date == today,
            )
        )
        fin = result.scalar_one_or_none()
        if not fin:
            fin = NatDailyFinancials(
                company_id=company_id,
                calendar_date=today,
                gross_revenue=0.0,
                opex=0.0,
                closed_profit=0.0,
            )
            session.add(fin)
        return fin

    @classmethod
    async def execute_npc_trade(
        cls,
        session: AsyncSession,
        company: NatCompany,
        item_id: str,
        action: str,
        quantity: float,
    ) -> Dict[str, Any]:
        action = action.upper()
        if not isfinite(float(quantity)) or quantity <= 0:
            return {"success": False, "reason": "invalid_quantity"}
        if action not in {"BUY", "SELL"}:
            return {"success": False, "reason": "invalid_action"}
        rounded_quantity = round(float(quantity), 2)
        if abs(float(quantity) - rounded_quantity) > 1e-9:
            return {
                "success": False,
                "reason": "invalid_quantity_precision",
                "message": "Количество можно указывать с точностью до 0,01.",
            }
        quantity = rounded_quantity

        quote = cls.get_npc_quote(item_id)
        from backend.natbirzha.services.creator_service import CreatorService
        effective_price = quote["npc_sell_price"] if action == "BUY" else quote["npc_buy_price"]
        allowed, restriction_error = await CreatorService.check_market_restriction(
            session, company.id, item_id, effective_price
        )
        if not allowed:
            return {
                "success": False,
                "reason": "market_restricted",
                "message": restriction_error,
                "price": effective_price,
            }
        locked = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        if not locked:
            return {"success": False, "reason": "company_not_found"}
        company = locked

        inv_result = await session.execute(
            select(NatInventory)
            .where(NatInventory.company_id == company.id, NatInventory.item_id == item_id)
            .with_for_update()
        )
        inv = inv_result.scalar_one_or_none()

        # Validate the business mutation before consuming scarce NPC daily quota.
        if action == "BUY":
            unit_price = quote["npc_sell_price"]
            total_cost = round(unit_price * quantity, 2)
            if company.cash < total_cost:
                return {
                    "success": False,
                    "reason": "insufficient_cash",
                    "needed": total_cost,
                    "available": company.cash,
                }
            existing = inv.quantity if inv else 0.0
            cap = await InventoryCapacityService.for_item(session, company, item_id)
            if existing + quantity > cap:
                return {
                    "success": False,
                    "reason": "inventory_overflow",
                    "item_id": item_id,
                    "capacity": cap,
                    "current": existing,
                    "incoming": quantity,
                }
        else:
            if not inv or inv.available_quantity < quantity:
                return {
                    "success": False,
                    "reason": "insufficient_inventory",
                    "needed": quantity,
                    "available": inv.available_quantity if inv else 0.0,
                }
            unit_price = quote["npc_buy_price"]
            total_payout = round(unit_price * quantity, 2)

        volume = await cls._reserve_volume(
            session,
            item_id,
            action,
            quantity,
            cash_amount=total_payout if action == "SELL" else None,
        )
        if not volume["success"]:
            rare_empty = action == "BUY" and volume["strict_reserve"]
            return {
                "success": False,
                "reason": "npc_rare_reserve_empty" if rare_empty else "npc_daily_quota_exceeded",
                "message": (
                    "Редкий запас Госрезерва на сегодня закончился"
                    if rare_empty else "Дневной лимит выкупа этого товара Госрезервом исчерпан"
                ),
                "daily_quota": volume["quota"],
                "daily_quota_cash": volume["quota_cash"],
                "remaining_quota": volume["remaining"],
                "remaining_npc_quota": volume["remaining"],
                "remaining_npc_cash_quota": volume["remaining_cash"],
                "quota_label": volume["quota_label"],
                "scaling_factor": volume["scaling_factor"],
            }

        fin = await cls._daily_financials(session, company.id)
        if action == "BUY":
            company.cash = round(company.cash - total_cost, 2)
            fin.opex = round(fin.opex + total_cost, 2)
            fin.closed_profit = round(fin.gross_revenue - fin.opex, 2)
            if not inv:
                inv = NatInventory(
                    company_id=company.id,
                    item_id=item_id,
                    quantity=0.0,
                    reserved_quantity=0.0,
                    avg_cost_basis=0.0,
                )
                session.add(inv)
            previous_value = inv.quantity * inv.avg_cost_basis
            inv.quantity = round(inv.quantity + quantity, 2)
            inv.avg_cost_basis = round((previous_value + total_cost) / inv.quantity, 2) if inv.quantity else 0.0
            await EconomyMetricsService.record(
                session, company_id=company.id, flow="SINK", category="npc_buy",
                cash_amount=total_cost, item_id=item_id, quantity=quantity,
            )
            await session.flush()
            return {
                "success": True,
                "action": action,
                "item_id": item_id,
                "unit_price": unit_price,
                "quantity": quantity,
                "total_cost": total_cost,
                "remaining_cash": company.cash,
                "daily_quota": volume["quota"],
                "remaining_npc_quota": volume["remaining"],
                "remaining_npc_cash_quota": volume["remaining_cash"],
                "daily_quota_cash": volume.get("quota_cash"),
                "quota_label": volume["quota_label"],
                "npc_scaling_factor": volume["scaling_factor"],
                "strict_reserve": bool(volume["strict_reserve"]),
            }

        seller_cogs = round(quantity * max(0.0, float(inv.avg_cost_basis or 0.0)), 6)
        inv.quantity = round(inv.quantity - quantity, 2)
        dividend_withheld = await DividendService.accrue_cash_inflow(
            session, company, total_payout
        )
        company.cash = round(company.cash + total_payout - dividend_withheld, 2)
        await CompanyProfitLedgerService.record(
            session,
            company.id,
            get_game_now(),
            revenue=total_payout,
            cost_of_goods_sold=seller_cogs,
        )
        fin.gross_revenue = round(fin.gross_revenue + total_payout, 2)
        fin.closed_profit = round(fin.gross_revenue - fin.opex, 2)
        xp_gain = max(1, int(quantity * 2))
        apply_xp(company, xp_gain)
        await EconomyMetricsService.record(
            session, company_id=company.id, flow="SOURCE", category="npc_sell",
            cash_amount=total_payout, item_id=item_id, quantity=quantity,
        )
        await session.flush()
        return {
            "success": True,
            "action": action,
            "item_id": item_id,
            "unit_price": unit_price,
            "quantity": quantity,
            "total_payout": total_payout,
            "new_cash_balance": company.cash,
            "xp_gained": xp_gain,
            "daily_quota": volume["quota"],
            "remaining_npc_quota": volume["remaining"],
            "remaining_npc_cash_quota": volume["remaining_cash"],
            "daily_quota_cash": volume.get("quota_cash"),
            "quota_label": volume["quota_label"],
            "npc_scaling_factor": volume["scaling_factor"],
            "strict_reserve": bool(volume["strict_reserve"]),
        }


__all__ = ["NPCReserveService"]
