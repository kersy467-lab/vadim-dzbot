"""Service managing active economic sabotages and crisis events."""

from __future__ import annotations

import asyncio
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
from backend.natbirzha.services.event_broadcaster import EventBroadcaster

logger = logging.getLogger(__name__)


class SabotageService:
    """Core domain service for launching, settling, and monitoring game crises."""

    MAX_ACTIVE_SABOTAGES = 2

    _cached_actives: List[Dict[str, Any]] = []
    _cached_sabotage_id: Optional[str] = None
    _cached_spec: Optional[Dict[str, Any]] = None
    _cached_ends_at: Optional[datetime] = None

    @classmethod
    def _update_cache(
        cls,
        actives: Any,
        now: Optional[datetime] = None,
    ) -> None:
        current = normalize_dt(now or get_game_now())
        if actives is None:
            raw_list = []
        elif isinstance(actives, (list, tuple)):
            raw_list = list(actives)
        else:
            raw_list = [actives]

        cached = []
        for a in raw_list:
            if not getattr(a, "is_active", False):
                continue
            ends_at = normalize_dt(getattr(a, "ends_at", None))
            if ends_at and ends_at > current:
                sab_id = getattr(a, "sabotage_id", None)
                cached.append({
                    "id": getattr(a, "id", None),
                    "sabotage_id": sab_id,
                    "title": getattr(a, "title", None),
                    "spec": get_sabotage_spec(sab_id) or {},
                    "ends_at": ends_at,
                })

        cls._cached_actives = cached
        if cached:
            cls._cached_sabotage_id = cached[0]["sabotage_id"]
            cls._cached_spec = cached[0]["spec"]
            cls._cached_ends_at = cached[0]["ends_at"]
        else:
            cls._cached_sabotage_id = None
            cls._cached_spec = None
            cls._cached_ends_at = None

    @classmethod
    def _is_cache_valid(cls, now: Optional[datetime] = None) -> bool:
        if not cls._cached_actives:
            return False
        current = normalize_dt(now or get_game_now())
        valid_items = [item for item in cls._cached_actives if item.get("ends_at") and item["ends_at"] > current]
        if len(valid_items) != len(cls._cached_actives):
            cls._cached_actives = valid_items
            if valid_items:
                cls._cached_sabotage_id = valid_items[0]["sabotage_id"]
                cls._cached_spec = valid_items[0]["spec"]
                cls._cached_ends_at = valid_items[0]["ends_at"]
            else:
                cls._cached_sabotage_id = None
                cls._cached_spec = None
                cls._cached_ends_at = None
        return bool(cls._cached_actives)

    @classmethod
    async def get_active_sabotages(
        cls, session: AsyncSession, *, now: Optional[datetime] = None
    ) -> List[NatActiveSabotage]:
        """Fetch all currently active sabotages from DB and sync in-memory cache."""
        current = normalize_dt(now or get_game_now())
        stmt = (
            select(NatActiveSabotage)
            .where(NatActiveSabotage.is_active == True)
            .order_by(NatActiveSabotage.id.desc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        valid_rows = []
        for row in rows:
            ends_at = normalize_dt(row.ends_at)
            if ends_at and ends_at <= current:
                row.is_active = False
                row.resolved_at = current
                row.resolved_by = "TIMEOUT"
                await session.flush()
            else:
                valid_rows.append(row)

        cls._update_cache(valid_rows, now=current)
        return valid_rows

    @classmethod
    async def get_active_sabotage(
        cls, session: AsyncSession, *, now: Optional[datetime] = None
    ) -> Optional[NatActiveSabotage]:
        """Fetch primary active sabotage (for backwards compatibility)."""
        actives = await cls.get_active_sabotages(session, now=now)
        return actives[0] if actives else None

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
        actives = await cls.get_active_sabotages(session, now=current)
        if any(a.sabotage_id == spec["id"] for a in actives):
            raise ValueError(f"Саботаж «{spec['name']}» уже активен в игре!")

        if len(actives) >= cls.MAX_ACTIVE_SABOTAGES:
            titles = " и ".join(f"«{a.title}»" for a in actives)
            raise ValueError(
                f"Уже активны {cls.MAX_ACTIVE_SABOTAGES} саботажа одновременно ({titles}). "
                f"Дождитесь окончания или завершите один из них."
            )

        duration = timedelta(hours=int(spec.get("duration_hours", 24)))
        ends_at = current + duration

        shock = float(spec.get("one_time_stock_shock", 0.0))
        affected_stocks = 0
        if shock != 0.0:
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
        
        all_actives = actives + [record]
        cls._update_cache(all_actives, now=current)

        if bot:
            await cls._broadcast_notice(
                session,
                bot,
                headline=spec["news_headline"],
                body=spec["news_body"],
            )

        asyncio.create_task(EventBroadcaster.broadcast_sabotage_start(spec))

        return {
            "success": True,
            "id": record.id,
            "sabotage_id": record.sabotage_id,
            "title": record.title,
            "started_at": record.started_at.isoformat(),
            "ends_at": record.ends_at.isoformat(),
            "duration_hours": spec["duration_hours"],
            "affected_stocks": affected_stocks,
            "active_count": len(all_actives),
        }

    @classmethod
    async def stop_sabotage(
        cls,
        session: AsyncSession,
        actor_id: int,
        *,
        sabotage_id: Optional[str] = None,
        reason: str = "CREATOR_ABORT",
        bot: Optional[Any] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Manually abort an ongoing crisis or a specific one if given."""
        current = normalize_dt(now or get_game_now())
        actives = await cls.get_active_sabotages(session, now=current)
        if not actives:
            raise ValueError("Сейчас нет активного саботажа.")

        if sabotage_id:
            clean_id = sabotage_id.strip().lower()
            matches = [a for a in actives if a.sabotage_id.lower() == clean_id]
            if not matches:
                raise ValueError(f"Саботаж '{sabotage_id}' сейчас не активен.")
            target = matches[0]
        else:
            target = actives[0]

        spec = get_sabotage_spec(target.sabotage_id) or {}
        target.is_active = False
        target.resolved_at = current
        target.resolved_by = reason
        target.cancelled_by_user_id = int(actor_id)
        await session.flush()

        remaining = [a for a in actives if a.id != target.id]
        cls._update_cache(remaining, now=current)

        headline = spec.get("end_headline", "✅ Кризис завершен досрочно")
        body = spec.get("end_body", "Государство нормализовало ситуацию в экономике.")
        if bot:
            await cls._broadcast_notice(session, bot, headline=headline, body=body)

        asyncio.create_task(
            EventBroadcaster.broadcast_sabotage_end(
                title=target.title,
                reason=reason,
                headline=headline,
                body=body,
            )
        )

        return {
            "success": True,
            "sabotage_id": target.sabotage_id,
            "title": target.title,
            "resolved_at": current.isoformat(),
            "reason": reason,
            "remaining_active_count": len(remaining),
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
        expired_list = (await session.execute(stmt)).scalars().all()
        if not expired_list:
            return None

        expired_info = []
        for expired in expired_list:
            spec = get_sabotage_spec(expired.sabotage_id) or {}
            expired.is_active = False
            expired.resolved_at = current
            expired.resolved_by = "TIMEOUT"
            await session.flush()

            headline = spec.get("end_headline", "✅ Экономический кризис подошел к концу")
            body = spec.get("end_body", "Рыночные показатели возвращаются в штатный режим.")
            if bot:
                await cls._broadcast_notice(session, bot, headline=headline, body=body)

            asyncio.create_task(
                EventBroadcaster.broadcast_sabotage_end(
                    title=expired.title,
                    reason="TIMEOUT",
                    headline=headline,
                    body=body,
                )
            )
            expired_info.append({"sabotage_id": expired.sabotage_id, "title": expired.title})

        remaining_stmt = (
            select(NatActiveSabotage)
            .where(NatActiveSabotage.is_active == True)
        )
        remaining = (await session.execute(remaining_stmt)).scalars().all()
        cls._update_cache(remaining, now=current)

        return {
            "expired": True,
            "count": len(expired_info),
            "expired_sabotages": expired_info,
            "sabotage_id": expired_info[0]["sabotage_id"] if expired_info else None,
            "title": expired_info[0]["title"] if expired_info else None,
        }

    @classmethod
    def get_income_multiplier(cls, specialization: Optional[str]) -> float:
        """Calculate compounded production/income multiplier for a given industry spec."""
        if not cls._is_cache_valid():
            return 1.0
        norm_spec = normalize_specialization(specialization or "")
        total_mult = 1.0
        for item in cls._cached_actives:
            spec = item.get("spec") or {}
            income_mults = spec.get("income_multipliers") or {}
            if norm_spec in income_mults:
                total_mult *= float(income_mults[norm_spec])
            else:
                total_mult *= float(spec.get("other_income_mult", 1.0))
        return round(total_mult, 4)

    @classmethod
    def get_resource_multiplier_sync(cls, item_id: str) -> float:
        """Calculate compounded base price multiplier for a resource."""
        if not cls._is_cache_valid():
            return 1.0
        clean_item = (item_id or "").strip().lower()
        total_mult = 1.0
        for item in cls._cached_actives:
            spec = item.get("spec") or {}
            res_mults = spec.get("resource_multipliers") or {}
            if clean_item in res_mults:
                total_mult *= float(res_mults[clean_item])
        return round(total_mult, 4)

    @classmethod
    def get_credit_rate_delta(cls) -> float:
        """Additive interest rate adjustment for state credits across active crises."""
        if not cls._is_cache_valid():
            return 0.0
        total_delta = 0.0
        for item in cls._cached_actives:
            spec = item.get("spec") or {}
            total_delta += float(spec.get("credit_rate_delta", 0.0))
        return round(total_delta, 4)

    @classmethod
    def are_new_credits_blocked(cls) -> bool:
        """Returns True if state credit applications are suspended by any crisis."""
        if not cls._is_cache_valid():
            return False
        return any(bool((item.get("spec") or {}).get("block_new_credits", False)) for item in cls._cached_actives)

    @classmethod
    def are_dividends_blocked(cls) -> bool:
        """Returns True if stock dividends cannot be paid out during any crisis."""
        if not cls._is_cache_valid():
            return False
        return any(bool((item.get("spec") or {}).get("block_dividends", False)) for item in cls._cached_actives)

    @classmethod
    def get_bond_price_multiplier(cls) -> float:
        """Price modifier compounded across active crises."""
        if not cls._is_cache_valid():
            return 1.0
        total_mult = 1.0
        for item in cls._cached_actives:
            spec = item.get("spec") or {}
            total_mult *= float(spec.get("bond_price_mult", 1.0))
        return round(total_mult, 4)

    @classmethod
    def get_active_summary(cls) -> Optional[Dict[str, Any]]:
        """Synchronous summary of current in-memory crises for read APIs."""
        if not cls._is_cache_valid():
            return None
        current = get_game_now()
        summaries = []
        for item in cls._cached_actives:
            spec = item.get("spec") or {}
            ends_at = item.get("ends_at")
            rem = max(0, int((ends_at - current).total_seconds())) if ends_at else 0
            summaries.append({
                "sabotage_id": item.get("sabotage_id"),
                "title": spec.get("name") or item.get("title"),
                "icon": spec.get("icon"),
                "description": spec.get("description"),
                "ends_at": ends_at.isoformat() if ends_at else None,
                "remaining_seconds": rem,
                "duration_hours": spec.get("duration_hours"),
                "details": spec,
            })
        if not summaries:
            return None

        primary = summaries[0]
        return {
            "active": True,
            "count": len(summaries),
            "max_allowed": cls.MAX_ACTIVE_SABOTAGES,
            "sabotages": summaries,
            # Backwards compatibility:
            "sabotage_id": primary["sabotage_id"],
            "title": primary["title"],
            "icon": primary["icon"],
            "description": primary["description"],
            "ends_at": primary["ends_at"],
            "remaining_seconds": primary["remaining_seconds"],
            "duration_hours": primary["duration_hours"],
            "details": primary["details"],
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
