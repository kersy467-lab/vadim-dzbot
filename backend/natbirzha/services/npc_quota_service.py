"""Shared daily quota accounting for purchases and sales with the State reserve."""

from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.natbirzha.config import get_game_today, nat_settings
from backend.natbirzha.models.inventory import (
    CANONICAL_ITEMS,
    get_npc_buy_price,
)
from backend.natbirzha.models.npc import NatNpcDailyVolume


class NPCQuotaMixin:
    @staticmethod
    async def get_active_player_scaling_factor(session: AsyncSession) -> float:
        # Kept for API compatibility. Regular NPC trading no longer scales down
        # with player count and therefore always reports a neutral factor.
        return 1.0

    @staticmethod
    async def get_daily_quota(
        session: AsyncSession,
        item_id: str | None = None,
        action: str | None = None,
    ) -> Dict[str, Any]:
        action = action.upper() if action else None
        reserve_cap = None
        if action == "BUY" and item_id:
            reserve_cap = nat_settings.NPC_RARE_SELL_RESERVES.get(item_id)
        elif action == "SELL" and item_id:
            # Лимиты на продажу товаров Госрезерву (NPC) сняты — выкуп неограничен
            reserve_cap = None
        quota = float(reserve_cap) if reserve_cap is not None else None
        cash_quota = None
        return {
            "scaling_factor": 1.0,
            "daily_quota_per_item": quota,
            "daily_quota": quota,
            "daily_quota_cash": cash_quota,
            "strict_reserve": reserve_cap is not None,
            "producer_quota": False,
            "liquidity_unlimited": reserve_cap is None,
        }

    @staticmethod
    def _quota_label(item_id: str, action: str, quota: float, remaining: float) -> str:
        unit = CANONICAL_ITEMS.get(item_id, {}).get("unit", "ед.")
        if action == "SELL":
            return "Госрезерв выкупает продукцию без ограничений"
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
                "remaining_npc_cash_quota": None,
                "quota_label": "Скупка Госрезервом: без ограничений" if action == "SELL" else "",
            }
        usage = await session.scalar(
            select(NatNpcDailyVolume).where(
                NatNpcDailyVolume.calendar_date == get_game_today(),
                NatNpcDailyVolume.item_id == item_id,
                NatNpcDailyVolume.action == action,
            )
        )
        if action == "SELL":
            unit_price = get_npc_buy_price(item_id)
            remaining_cash = max(
                0.0,
                round(
                    float(nat_settings.NPC_DAILY_BUYBACK_CASH_LIMIT)
                    - (float(usage.used_cash) if usage else 0.0),
                    2,
                ),
            )
            remaining = remaining_cash / max(0.01, unit_price)
        else:
            used = float(usage.used_quantity) if usage else 0.0
            remaining = max(0.0, float(quota) - used)
            remaining_cash = None
        return {
            **quota_info,
            "remaining_npc_quota": remaining,
            "remaining_npc_cash_quota": remaining_cash,
            "quota_label": cls._quota_label(item_id, action, float(quota), remaining),
        }

    @classmethod
    async def _reserve_volume(
        cls,
        session: AsyncSession,
        item_id: str,
        action: str,
        quantity: float,
        cash_amount: float | None = None,
    ) -> Dict[str, Any]:
        today = get_game_today()
        quota_info = await cls.get_daily_quota(session, item_id, action)
        quota = quota_info["daily_quota_per_item"]
        if quota is None:
            return {
                "success": 1.0,
                "quota": None,
                "quota_cash": None,
                "remaining": None,
                "remaining_cash": None,
                "scaling_factor": 1.0,
                "strict_reserve": False,
                "producer_quota": False,
                "quota_label": "Скупка Госрезервом: без ограничений" if action == "SELL" else "",
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
                        used_cash=0.0,
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
        if action == "SELL":
            unit_price = get_npc_buy_price(item_id)
            cash_limit = float(nat_settings.NPC_DAILY_BUYBACK_CASH_LIMIT)
            payout_cash = max(0.0, round(float(cash_amount or 0.0), 2))
            remaining_cash = max(0.0, round(cash_limit - float(usage.used_cash), 2))
            remaining = remaining_cash / max(0.01, unit_price)
        else:
            remaining = max(0.0, quota - float(usage.used_quantity))
        if quantity > remaining or (action == "SELL" and payout_cash > remaining_cash):
            return {
                "success": 0.0,
                "quota": quota,
                "quota_cash": quota_info["daily_quota_cash"],
                "remaining": remaining,
                "remaining_cash": remaining_cash if action == "SELL" else None,
                "scaling_factor": quota_info["scaling_factor"],
                "strict_reserve": quota_info["strict_reserve"],
                "producer_quota": quota_info["producer_quota"],
                "quota_label": cls._quota_label(item_id, action, quota, remaining),
            }

        usage.used_quantity = float(usage.used_quantity) + float(quantity)
        if action == "SELL":
            usage.used_cash = round(float(usage.used_cash) + payout_cash, 2)
            remaining_cash = max(0.0, round(cash_limit - float(usage.used_cash), 2))
            remaining = remaining_cash / max(0.01, unit_price)
        else:
            remaining = max(0.0, quota - float(usage.used_quantity))
        return {
            "success": 1.0,
            "quota": quota,
            "quota_cash": quota_info["daily_quota_cash"],
            "remaining": remaining,
            "remaining_cash": remaining_cash if action == "SELL" else None,
            "scaling_factor": quota_info["scaling_factor"],
            "strict_reserve": quota_info["strict_reserve"],
            "producer_quota": quota_info["producer_quota"],
            "quota_label": cls._quota_label(item_id, action, quota, remaining),
        }


__all__ = ["NPCQuotaMixin"]
