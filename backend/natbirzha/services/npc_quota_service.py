"""Daily NPC supply limits and per-company State reserve buyback caps."""

from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.natbirzha.config import get_game_today, nat_settings
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, get_npc_buy_price
from backend.natbirzha.models.npc import NatNpcCompanyDailyVolume, NatNpcDailyVolume


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
        *,
        company_id: int | None = None,
    ) -> Dict[str, Any]:
        action = action.upper() if action else None
        company_cash_cap = None
        if action == "SELL" and item_id:
            company_cash_cap = nat_settings.NPC_COMPANY_DAILY_BUYBACK_CASH_LIMITS.get(item_id)
        # Companies can buy any quantity from NPCs. Daily caps apply only to
        # NPC purchases from companies (action == SELL), never to player buys.
        reserve_cap = None
        if company_cash_cap is not None:
            quota = float(company_cash_cap) / max(0.01, get_npc_buy_price(item_id))
        else:
            quota = float(reserve_cap) if reserve_cap is not None else None
        return {
            "scaling_factor": 1.0,
            "daily_quota_per_item": quota,
            "daily_quota": quota,
            "daily_quota_cash": float(company_cash_cap) if company_cash_cap is not None else None,
            "strict_reserve": reserve_cap is not None,
            "company_specific": company_cash_cap is not None,
            "producer_quota": False,
            "liquidity_unlimited": reserve_cap is None and company_cash_cap is None,
        }

    @staticmethod
    def _quota_label(item_id: str, action: str, quota: float, remaining: float) -> str:
        unit = CANONICAL_ITEMS.get(item_id, {}).get("unit", "ед.")
        if action == "SELL":
            return f"Осталось выкупить сегодня: {remaining:.2f} {unit}"
        return f"Редкий запас Госрезерва сегодня: {remaining:g} из {quota:g} {unit}"

    @classmethod
    async def get_quota_status(
        cls,
        session: AsyncSession,
        item_id: str,
        action: str,
        *,
        company_id: int | None = None,
    ) -> Dict[str, Any]:
        return (await cls.get_quota_statuses(
            session, [item_id], action, company_id=company_id
        ))[item_id]

    @classmethod
    async def get_quota_statuses(
        cls,
        session: AsyncSession,
        item_ids: list[str],
        action: str,
        *,
        company_id: int | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        action = action.upper()
        quota_info_by_item = {
            item_id: await cls.get_daily_quota(
                session, item_id, action, company_id=company_id
            )
            for item_id in item_ids
        }
        limited_item_ids = [
            item_id for item_id, quota_info in quota_info_by_item.items()
            if quota_info["daily_quota"] is not None
        ]
        company_limited_ids = [
            item_id for item_id in limited_item_ids
            if quota_info_by_item[item_id].get("company_specific")
        ]
        global_limited_ids = [
            item_id for item_id in limited_item_ids
            if not quota_info_by_item[item_id].get("company_specific")
        ]
        company_usage_by_item = {}
        if company_limited_ids and company_id is not None:
            usages = (await session.execute(
                select(NatNpcCompanyDailyVolume).where(
                    NatNpcCompanyDailyVolume.calendar_date == get_game_today(),
                    NatNpcCompanyDailyVolume.company_id == company_id,
                    NatNpcCompanyDailyVolume.item_id.in_(company_limited_ids),
                )
            )).scalars().all()
            company_usage_by_item = {usage.item_id: usage for usage in usages}
        global_usage_by_item = {}
        if global_limited_ids:
            usages = (await session.execute(
                select(NatNpcDailyVolume).where(
                    NatNpcDailyVolume.calendar_date == get_game_today(),
                    NatNpcDailyVolume.item_id.in_(global_limited_ids),
                    NatNpcDailyVolume.action == action,
                )
            )).scalars().all()
            global_usage_by_item = {usage.item_id: usage for usage in usages}

        statuses = {}
        for item_id, quota_info in quota_info_by_item.items():
            quota = quota_info["daily_quota"]
            if quota is None:
                statuses[item_id] = {
                    **quota_info,
                    "remaining_npc_quota": None,
                    "remaining_npc_cash_quota": None,
                    "quota_label": "Скупка Госрезервом: без ограничений" if action == "SELL" else "",
                }
                continue
            if action == "SELL":
                cash_limit = float(quota_info["daily_quota_cash"] or 0.0)
                usage = company_usage_by_item.get(item_id)
                unit_price = max(0.01, get_npc_buy_price(item_id))
                remaining_cash = max(
                    0.0,
                    round(cash_limit - (float(usage.used_cash) if usage else 0.0), 2),
                )
                remaining = remaining_cash / unit_price
                unit = CANONICAL_ITEMS.get(item_id, {}).get("unit", "ед.")
                label = f"Осталось сегодня: {remaining_cash:.0f} cash · до {remaining:.2f} {unit}"
            else:
                usage = global_usage_by_item.get(item_id)
                used = float(usage.used_quantity) if usage else 0.0
                remaining = max(0.0, float(quota) - used)
                remaining_cash = None
                label = cls._quota_label(item_id, action, float(quota), remaining)
            statuses[item_id] = {
                **quota_info,
                "remaining_npc_quota": remaining,
                "remaining_npc_cash_quota": remaining_cash,
                "quota_label": label,
            }
        return statuses

    @classmethod
    async def _reserve_volume(
        cls,
        session: AsyncSession,
        item_id: str,
        action: str,
        quantity: float,
        cash_amount: float | None = None,
        *,
        company_id: int | None = None,
    ) -> Dict[str, Any]:
        today = get_game_today()
        quota_info = await cls.get_daily_quota(
            session, item_id, action, company_id=company_id
        )
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
        if quota_info.get("company_specific"):
            if company_id is None:
                raise ValueError("Company ID is required for company-specific NPC buyback limits")
            result = await session.execute(
                select(NatNpcCompanyDailyVolume)
                .where(
                    NatNpcCompanyDailyVolume.calendar_date == today,
                    NatNpcCompanyDailyVolume.company_id == company_id,
                    NatNpcCompanyDailyVolume.item_id == item_id,
                )
                .with_for_update()
            )
            usage = result.scalar_one_or_none()
            if not usage:
                try:
                    async with session.begin_nested():
                        usage = NatNpcCompanyDailyVolume(
                            calendar_date=today,
                            company_id=company_id,
                            item_id=item_id,
                            used_cash=0.0,
                        )
                        session.add(usage)
                        await session.flush()
                except IntegrityError:
                    result = await session.execute(
                        select(NatNpcCompanyDailyVolume)
                        .where(
                            NatNpcCompanyDailyVolume.calendar_date == today,
                            NatNpcCompanyDailyVolume.company_id == company_id,
                            NatNpcCompanyDailyVolume.item_id == item_id,
                        )
                        .with_for_update()
                    )
                    usage = result.scalar_one()
            unit_price = max(0.01, get_npc_buy_price(item_id))
            cash_limit = float(quota_info["daily_quota_cash"] or 0.0)
            payout_cash = max(0.0, round(float(cash_amount or 0.0), 2))
            remaining_cash = max(0.0, round(cash_limit - float(usage.used_cash), 2))
            remaining = remaining_cash / unit_price
            if payout_cash > remaining_cash + 1e-9 or quantity > remaining + 1e-9:
                return {
                    "success": 0.0,
                    "quota": quota,
                    "quota_cash": cash_limit,
                    "remaining": remaining,
                    "remaining_cash": remaining_cash,
                    "scaling_factor": quota_info["scaling_factor"],
                    "strict_reserve": False,
                    "producer_quota": False,
                    "quota_label": f"Осталось сегодня: {remaining_cash:.0f} cash",
                }
            usage.used_cash = round(float(usage.used_cash) + payout_cash, 2)
            remaining_cash = max(0.0, round(cash_limit - float(usage.used_cash), 2))
            remaining = remaining_cash / unit_price
            unit = CANONICAL_ITEMS.get(item_id, {}).get("unit", "ед.")
            return {
                "success": 1.0,
                "quota": quota,
                "quota_cash": cash_limit,
                "remaining": remaining,
                "remaining_cash": remaining_cash,
                "scaling_factor": quota_info["scaling_factor"],
                "strict_reserve": False,
                "producer_quota": False,
                "quota_label": f"Осталось сегодня: {remaining_cash:.0f} cash · до {remaining:.2f} {unit}",
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
            cash_limit = float(quota_info["daily_quota_cash"] or 0.0)
            payout_cash = max(0.0, round(float(cash_amount or 0.0), 2))
            remaining_cash = max(0.0, round(cash_limit - float(usage.used_cash), 2))
            quantity_remaining = max(0.0, float(quota) - float(usage.used_quantity))
            remaining = min(quantity_remaining, remaining_cash / max(0.01, unit_price))
        else:
            remaining = max(0.0, quota - float(usage.used_quantity))
        if quantity > remaining + 1e-9 or (action == "SELL" and payout_cash > remaining_cash + 0.01):
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
            quantity_remaining = max(0.0, float(quota) - float(usage.used_quantity))
            remaining = min(quantity_remaining, remaining_cash / max(0.01, unit_price))
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
