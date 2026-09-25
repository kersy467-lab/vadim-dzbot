"""Service managing active economic sabotages and crisis events."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.sabotages import (
    SABOTAGES_CATALOG,
    get_sabotage_spec,
    normalize_specialization,
)
from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.sabotage import NatActiveSabotage
from backend.natbirzha.models.stocks import NatStock, NatStockPriceSnapshot

logger = logging.getLogger(__name__)


class SabotageService:
    """Core domain service for launching, settling, and monitoring game crises."""

    _cached_sabotage_id: Optional[str] = None
    _cached_spec: Optional[Dict[str, Any]] = None
    _cached_ends_at: Optional[datetime] = None

    @classmethod
    def _update_cache(cls, active: Optional[NatActiveSabotage], now: Optional[datetime] = None) -> None:
        current = normalize_dt(now or get_game_now())
        if active and active.is_active:
            ends_at = normalize_dt(active.ends_at)
            if ends_at and ends_at > current:
                cls._cached_sabotage_id = active.sabotage_id
                cls._cached_spec = get_sabotage_spec(active.sabotage_id)
                cls._cached_ends_at = ends_at
                return
        cls._cached_sabotage_id = None
        cls._cached_spec = None
        cls._cached_ends_at = None

    @classmethod
    def _is_cache_valid(cls, now: Optional[datetime] = None) -> bool:
        if not cls._cached_sabotage_id or not cls._cached_ends_at or not cls._cached_spec:
            return False
        current = normalize_dt(now or get_game_now())
        if current >= cls._cached_ends_at:
            cls._cached_sabotage_id = None
            cls._cached_spec = None
            cls._cached_ends_at = None
            return False
        return True

    @classmethod
    async def get_active_sabotage(
        cls, session: AsyncSession, *, now: Optional[datetime] = None
    ) -> Optional[NatActiveSabotage]:
        """Fetch currently active sabotage from DB and sync in-memory cache."""
        current = normalize_dt(now or get_game_now())
        stmt = (
            select(NatActiveSabotage)
            .where(NatActiveSabotage.is_active == True)
            .order_by(NatActiveSabotage.id.desc())
        )
        row = (await session.execute(stmt)).scalars().first()
        if row:
            ends_at = normalize_dt(row.ends_at)
            if ends_at and ends_at <= current:
                row.is_active = False
                row.resolved_at = current
                row.resolved_by = "TIMEOUT"
                await session.flush()
                cls._update_cache(None, now=current)
                return None
            cls._update_cache(row, now=current)
            return row
        cls._update_cache(None, now=current)
        return None

    @classmethod
    async def start_sabotage(
        cls,
        session: AsyncSession,
        sabotage_id: str,
        actor_id: int,
        *,
        bot: Optional[Any] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Activate a crisis event, shock stocks if applicable, and notify players."""
        spec = get_sabotage_spec(sabotage_id)
        if not spec:
            raise ValueError(f"Неизвестный саботаж: '{sabotage_id}'")

        current = normalize_dt(now or get_game_now())
        active = await cls.get_active_sabotage(session, now=current)
        if active:
            raise ValueError(
                f"Уже активен саботаж: «{active.title}». "
                f"Дождитесь окончания или завершите его досрочно."
            )

        duration = timedelta(hours=int(spec.get("duration_hours", 24)))
        ends_at = current + duration

        shock = float(spec.get("one_time_stock_shock", 0.0))
        affected_stocks = 0
        if shock < 0:
            stocks_stmt = select(NatStock).where(NatStock.is_listed == True).with_for_update()
            stocks = (await session.execute(stocks_stmt)).scalars().all()
            for stock in stocks:
                new_price = max(0.01, round(float(stock.current_price) * (1.0 + shock), 2))
                new_val = round(new_price * float(stock.total_shares), 2)
                stock.current_price = new_price
                stock.last_valuation = new_val
                stock.valuation_updated_at = current
                session.add(
                    NatStockPriceSnapshot(
                        stock_id=stock.id,
                        price=new_price,
                        valuation=new_val,
                        captured_at=current,
                    )
                )
                affected_stocks += 1

        record = NatActiveSabotage(
            sabotage_id=spec["id"],
            title=spec["name"],
            started_at=current,
            ends_at=ends_at,
            started_by_user_id=int(actor_id),
            is_active=True,
            details_json=spec,
        )
        session.add(record)
        await session.flush()
        cls._update_cache(record, now=current)

        if bot:
            await cls._broadcast_notice(
                session,
                bot,
                headline=spec["news_headline"],
                body=spec["news_body"],
            )

        return {
            "success": True,
            "id": record.id,
            "sabotage_id": record.sabotage_id,
            "title": record.title,
            "started_at": record.started_at.isoformat(),
            "ends_at": record.ends_at.isoformat(),
            "duration_hours": spec["duration_hours"],
            "affected_stocks": affected_stocks,
        }

    @classmethod
    async def stop_sabotage(
        cls,
        session: AsyncSession,
        actor_id: int,
        *,
        reason: str = "CREATOR_ABORT",
        bot: Optional[Any] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Manually abort the ongoing crisis."""
        current = normalize_dt(now or get_game_now())
        active = await cls.get_active_sabotage(session, now=current)
        if not active:
            raise ValueError("Сейчас нет активного саботажа.")

        spec = get_sabotage_spec(active.sabotage_id) or {}
        active.is_active = False
        active.resolved_at = current
        active.resolved_by = reason
        active.cancelled_by_user_id = int(actor_id)
        await session.flush()
        cls._update_cache(None, now=current)

        if bot:
            headline = spec.get("end_headline", "✅ Кризис завершен досрочно")
            body = spec.get("end_body", "Государство нормализовало ситуацию в экономике.")
            await cls._broadcast_notice(session, bot, headline=headline, body=body)

        return {
            "success": True,
            "sabotage_id": active.sabotage_id,
            "title": active.title,
            "resolved_at": current.isoformat(),
            "reason": reason,
        }

    @classmethod
    async def check_and_expire(
        cls,
        session: AsyncSession,
        *,
        bot: Optional[Any] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Periodic hook to deactivate elapsed crises and notify players."""
        current = normalize_dt(now or get_game_now())
        stmt = (
            select(NatActiveSabotage)
            .where(
                NatActiveSabotage.is_active == True,
                NatActiveSabotage.ends_at <= current,
            )
            .with_for_update()
        )
        expired = (await session.execute(stmt)).scalars().first()
        if not expired:
            return None

        spec = get_sabotage_spec(expired.sabotage_id) or {}
        expired.is_active = False
        expired.resolved_at = current
        expired.resolved_by = "TIMEOUT"
        await session.flush()
        cls._update_cache(None, now=current)

        if bot:
            headline = spec.get("end_headline", "✅ Экономический кризис подошел к концу")
            body = spec.get("end_body", "Рыночные показатели возвращаются в штатный режим.")
            await cls._broadcast_notice(session, bot, headline=headline, body=body)

        return {
            "expired": True,
            "sabotage_id": expired.sabotage_id,
            "title": expired.title,
        }

    @classmethod
    def get_income_multiplier(cls, specialization: Optional[str]) -> float:
        """Calculate production/income multiplier for a given industry spec."""
        if not cls._is_cache_valid():
            return 1.0
        spec = cls._cached_spec or {}
        income_mults = spec.get("income_multipliers") or {}
        norm_spec = normalize_specialization(specialization or "")
        if norm_spec in income_mults:
            return float(income_mults[norm_spec])
        if income_mults:
            return float(spec.get("other_income_mult", 1.0))
        return float(spec.get("other_income_mult", 1.0))

    @classmethod
    def get_resource_multiplier_sync(cls, item_id: str) -> float:
        """Calculate base price multiplier for a resource."""
        if not cls._is_cache_valid():
            return 1.0
        spec = cls._cached_spec or {}
        res_mults = spec.get("resource_multipliers") or {}
        clean_item = (item_id or "").strip().lower()
        if clean_item in res_mults:
            return float(res_mults[clean_item])
        return 1.0

    @classmethod
    def get_credit_rate_delta(cls) -> float:
        """Additive interest rate adjustment for state credits."""
        if not cls._is_cache_valid():
            return 0.0
        spec = cls._cached_spec or {}
        return float(spec.get("credit_rate_delta", 0.0))

    @classmethod
    def are_new_credits_blocked(cls) -> bool:
        """Returns True if state credit applications are suspended."""
        if not cls._is_cache_valid():
            return False
        spec = cls._cached_spec or {}
        return bool(spec.get("block_new_credits", False))

    @classmethod
    def are_dividends_blocked(cls) -> bool:
        """Returns True if stock dividends cannot be paid out during default."""
        if not cls._is_cache_valid():
            return False
        spec = cls._cached_spec or {}
        return bool(spec.get("block_dividends", False))

    @classmethod
    def get_bond_price_multiplier(cls) -> float:
        """Price modifier for primary and secondary bond purchases."""
        if not cls._is_cache_valid():
            return 1.0
        spec = cls._cached_spec or {}
        return float(spec.get("bond_price_mult", 1.0))

    @classmethod
    def get_active_summary(cls) -> Optional[Dict[str, Any]]:
        """Synchronous summary of current in-memory crisis for read APIs."""
        if not cls._is_cache_valid():
            return None
        spec = cls._cached_spec or {}
        current = get_game_now()
        ends_at = cls._cached_ends_at
        rem = max(0, int((ends_at - current).total_seconds())) if ends_at else 0
        return {
            "active": True,
            "sabotage_id": cls._cached_sabotage_id,
            "title": spec.get("name"),
            "icon": spec.get("icon"),
            "description": spec.get("description"),
            "ends_at": ends_at.isoformat() if ends_at else None,
            "remaining_seconds": rem,
            "duration_hours": spec.get("duration_hours"),
            "details": spec,
        }

    @staticmethod
    async def _broadcast_notice(
        session: AsyncSession, bot: Any, *, headline: str, body: str
    ) -> None:
        """Helper to send announcement to all players with a company."""
        from backend.bot.handlers.admin.natbirzha_notice import _get_natbirzha_recipient_ids
        try:
            recipient_ids = await _get_natbirzha_recipient_ids(session)
        except Exception:
            logger.exception("Could not retrieve Natbirzha recipients for crisis notice")
            return

        message_text = f"📢 <b>НАТБИРЖА: ГОСУДАРСТВЕННЫЙ ВЕСТНИК</b>\n\n<b>{headline}</b>\n\n{body}"
        for tg_id in recipient_ids:
            try:
                await bot.send_message(chat_id=tg_id, text=message_text, parse_mode="HTML")
            except Exception:
                pass


__all__ = ["SabotageService"]
