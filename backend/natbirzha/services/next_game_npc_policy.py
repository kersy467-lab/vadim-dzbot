"""NPC purchasing policy inherited from the current economic game."""
from datetime import timedelta
from sqlalchemy import select, func
from backend.natbirzha.models.next_game import NatNextGameLedger
from backend.natbirzha.services.next_game_service.common import _utcnow

DAILY_UTILITY_PAYOUT = 300_000


async def remaining_buyback(session, company_id, item_id, now=None):
    if item_id not in {"water", "energy"}:
        return None
    current = now or _utcnow()
    start = current.replace(hour=6, minute=0, second=0, microsecond=0)
    if start > current:
        start -= timedelta(days=1)
    paid = await session.scalar(select(func.coalesce(func.sum(NatNextGameLedger.cash_company_delta), 0))
        .where(NatNextGameLedger.company_id == company_id, NatNextGameLedger.action == "SELL",
            NatNextGameLedger.item_id == item_id, NatNextGameLedger.created_at >= start,
            NatNextGameLedger.created_at < start + timedelta(days=1)))
    return round(max(0, DAILY_UTILITY_PAYOUT - float(paid)), 2)
