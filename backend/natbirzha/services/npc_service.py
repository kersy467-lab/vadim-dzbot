from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.natbirzha.config import get_game_today, nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import (
    CANONICAL_ITEMS,
    NatInventory,
    get_item_base_price,
    get_npc_buy_price,
    get_npc_sell_price,
)
from backend.natbirzha.models.npc import NatNpcDailyVolume
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.services.progression_service import apply_xp
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService


class NPCReserveService:
    """State reserve with a fixed price corridor and no regular daily liquidity cap."""

    @staticmethod
    def get_npc_quote(item_id: str) -> Dict[str, Any]:
        if item_id not in CANONICAL_ITEMS:
            raise ValueError(f"Unknown item: {item_id}")
        base = get_item_base_price(item_id)
        buy_floor = get_npc_buy_price(item_id)
        sell_cap = get_npc_sell_price(item_id)
        return {
            "item_id": item_id,
            "name": CANONICAL_ITEMS[item_id]["name"],
            "unit": CANONICAL_ITEMS[item_id]["unit"],
            "base_price": base,
            "npc_buy_price": buy_floor,
            "npc_sell_price": sell_cap,
            "spread_pct": round(((sell_cap - buy_floor) / base) * 100, 1),
        }

    @staticmethod
    async def get_active_player_scaling_factor(session: AsyncSession) -> float:
        # Kept for API compatibility. Regular NPC trading no longer scales down
        # with player count and therefore always reports a neutral factor.
        return 1.0

    @classmethod
    async def get_daily_quota(
        cls,
        session: AsyncSession,
        item_id: str | None = None,
        action: str | None = None,
    ) -> Dict[str, Any]:
        action = action.upper() if action else None
        reserve_cap = None
        if action == "BUY" and item_id:
            reserve_cap = nat_settings.NPC_RARE_SELL_RESERVES.get(item_id)
        quota = float(reserve_cap) if reserve_cap is not None else None
        return {
            "scaling_factor": 1.0,
            "daily_quota_per_item": quota,
            "daily_quota": quota,
            "strict_reserve": reserve_cap is not None,
            "producer_quota": False,
            "liquidity_unlimited": reserve_cap is None,
        }

    @staticmethod
    def _quota_label(item_id: str, action: str, quota: float, remaining: float) -> str:
        unit = CANONICAL_ITEMS.get(item_id, {}).get("unit", "ед.")
        return f"Редкий запас Госрезерва сегодня: {remaining:g} из {quota:g} {unit}"

    @classmethod
    async def get_quota_status(
        cls,
        session: AsyncSession,
        item_id: str,
        action: str,
    ) -> Dict[str, Any]:
        action = action.upper()
        quota_info = await cls.get_daily_quota(session, item_id, action)
        quota = quota_info["daily_quota"]
        if quota is None:
            return {
                **quota_info,
                "remaining_npc_quota": None,
                "quota_label": "",
            }
        used = (await session.execute(
            select(NatNpcDailyVolume.used_quantity).where(
                NatNpcDailyVolume.calendar_date == get_game_today(),
                NatNpcDailyVolume.item_id == item_id,
                NatNpcDailyVolume.action == action,
            )
        )).scalar_one_or_none() or 0.0
        remaining = max(0.0, round(float(quota) - float(used), 2))
        return {
            **quota_info,
            "remaining_npc_quota": remaining,
            "quota_label": cls._quota_label(item_id, action, float(quota), remaining),
        }

    @classmethod
    async def _reserve_volume(
        cls,
        session: AsyncSession,
        item_id: str,
        action: str,
        quantity: float,
    ) -> Dict[str, Any]:
        today = get_game_today()
        quota_info = await cls.get_daily_quota(session, item_id, action)
        quota = quota_info["daily_quota_per_item"]
        if quota is None:
            return {
                "success": 1.0,
                "quota": None,
                "remaining": None,
                "scaling_factor": 1.0,
                "strict_reserve": False,
                "producer_quota": False,
                "quota_label": "",
            }
        result = await session.execute(
            select(NatNpcDailyVolume)
            .where(
                NatNpcDailyVolume.calendar_date == today,
                NatNpcDailyVolume.item_id == item_id,
                NatNpcDailyVolume.action == action,
            )
            .with_for_update()
        )
        usage = result.scalar_one_or_none()
        if not usage:
            try:
                async with session.begin_nested():
                    usage = NatNpcDailyVolume(
                        calendar_date=today,
                        item_id=item_id,
                        action=action,
                        used_quantity=0.0,
                    )
                    session.add(usage)
                    await session.flush()
            except IntegrityError:
                # Another worker created the daily counter first. Re-read and lock it.
                result = await session.execute(
                    select(NatNpcDailyVolume)
                    .where(
                        NatNpcDailyVolume.calendar_date == today,
                        NatNpcDailyVolume.item_id == item_id,
                        NatNpcDailyVolume.action == action,
                    )
                    .with_for_update()
                )
                usage = result.scalar_one()
        remaining = max(0.0, round(quota - usage.used_quantity, 2))
        if quantity > remaining:
            return {
                "success": 0.0,
                "quota": quota,
                "remaining": remaining,
                "scaling_factor": quota_info["scaling_factor"],
                "strict_reserve": quota_info["strict_reserve"],
                "producer_quota": quota_info["producer_quota"],
                "quota_label": cls._quota_label(item_id, action, quota, remaining),
            }
        usage.used_quantity = round(usage.used_quantity + quantity, 2)
        remaining = round(quota - usage.used_quantity, 2)
        return {
            "success": 1.0,
            "quota": quota,
            "remaining": remaining,
            "scaling_factor": quota_info["scaling_factor"],
            "strict_reserve": quota_info["strict_reserve"],
            "producer_quota": quota_info["producer_quota"],
            "quota_label": cls._quota_label(item_id, action, quota, remaining),
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
        if quantity <= 0:
            return {"success": False, "reason": "invalid_quantity"}
        if action not in {"BUY", "SELL"}:
            return {"success": False, "reason": "invalid_action"}

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
            cap = float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM)
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

        volume = await cls._reserve_volume(session, item_id, action, quantity)
        if not volume["success"]:
            return {
                "success": False,
                "reason": "npc_rare_reserve_empty",
                "message": "Редкий запас Госрезерва на сегодня закончился",
                "daily_quota": volume["quota"],
                "remaining_quota": volume["remaining"],
                "remaining_npc_quota": volume["remaining"],
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
                "quota_label": volume["quota_label"],
                "npc_scaling_factor": volume["scaling_factor"],
                "strict_reserve": bool(volume["strict_reserve"]),
            }

        inv.quantity = round(inv.quantity - quantity, 2)
        company.cash = round(company.cash + total_payout, 2)
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
            "quota_label": volume["quota_label"],
            "npc_scaling_factor": volume["scaling_factor"],
            "strict_reserve": bool(volume["strict_reserve"]),
        }


__all__ = ["NPCReserveService"]
