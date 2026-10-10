"""Bounded treasury financing backed by locked next-game sell inventory."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameMarketTrade
from backend.natbirzha.models.next_game_advance import NatNextGameMarketAdvance
from backend.natbirzha.next_game_catalog import get_next_game_items
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_service.common import SELL_MARKDOWN

ADVANCE_LIMIT = 30_000.0
MIN_REFERENCE_TURNOVER = 1_000.0


class NextGameAdvanceService:
    @classmethod
    async def reference(cls, session, item_id, owner_company_id=None, *, now=None):
        current = now or datetime.now(timezone.utc).replace(tzinfo=None)
        buyer, seller = aliased(NatNextGameCompany), aliased(NatNextGameCompany)
        trade = NatNextGameMarketTrade
        query = select(trade).join(buyer, buyer.id == trade.buyer_company_id).join(
            seller, seller.id == trade.seller_company_id,
        ).where(trade.item_id == item_id, buyer.owner_tg_id != seller.owner_tg_id,
                trade.executed_at >= current - timedelta(hours=24), trade.executed_at <= current)
        if owner_company_id is not None:
            query = query.where(trade.buyer_company_id != owner_company_id,
                                trade.seller_company_id != owner_company_id)
        history = (await session.scalars(query.order_by(
            trade.executed_at.desc(), trade.id.desc(),
        ).limit(48))).all()
        pairs = {tuple(sorted((row.buyer_company_id, row.seller_company_id))) for row in history}
        turnover = sum(row.price * row.quantity for row in history)
        if len(history) < 3 or len(pairs) < 2 or turnover < MIN_REFERENCE_TURNOVER:
            return None
        # A manipulated last print cannot lift collateral above the NPC buyback.
        npc_buyback = round(get_next_game_items()[item_id]["base_price"] * SELL_MARKDOWN, 2)
        return round(min(history[0].price, median(row.price for row in history), npc_buyback), 4)

    @classmethod
    async def fund(cls, session, company, order, *, now=None):
        if order.side != "SELL" or order.remaining_quantity <= 0:
            return 0.0
        reference = await cls.reference(session, order.item_id, company.id, now=now)
        if reference is None or order.limit_price > reference + 1e-9:
            return 0.0
        outstanding = await session.scalar(select(func.coalesce(func.sum(
            NatNextGameMarketAdvance.outstanding_amount), 0)).where(
            NatNextGameMarketAdvance.company_id == company.id,
        ))
        treasury = await NextGameService._treasury(session)
        available = await NextGameService._available_treasury_cash(session, treasury)
        value = min(max(0, ADVANCE_LIMIT - outstanding), available,
                    order.remaining_quantity * order.limit_price)
        paid = float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN))
        if paid < 0.01:
            return 0.0
        treasury.cash = round(treasury.cash - paid, 8)
        company.cash = round(company.cash + paid, 8)
        session.add(NatNextGameMarketAdvance(
            order_id=order.id, company_id=company.id, advance_paid=paid,
            outstanding_amount=paid, reference_price=reference,
            created_at=now or datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        session.add(NextGameService._ledger(
            company.id, "MARKET_ADVANCE", paid, -paid, item_id=order.item_id,
            metadata={"order_id": order.id, "reference_price": reference},
        ))
        await session.flush()
        return paid

    @staticmethod
    async def repay_fill(session, order, cash):
        funding = await session.get(NatNextGameMarketAdvance, order.id)
        if funding is None or funding.outstanding_amount <= 1e-8:
            return 0.0
        repayment = round(min(funding.outstanding_amount, cash), 8)
        funding.outstanding_amount = max(0, round(funding.outstanding_amount - repayment, 8))
        treasury = await NextGameService._treasury(session)
        treasury.cash = round(treasury.cash + repayment, 8)
        session.add(NextGameService._ledger(
            order.company_id, "ADVANCE_REPAID", -repayment, repayment,
            item_id=order.item_id, metadata={"order_id": order.id},
        ))
        return repayment

    @staticmethod
    async def decorate_orders(session, payloads):
        ids = [row["id"] for row in payloads]
        if not ids:
            return payloads
        rows = (await session.scalars(select(NatNextGameMarketAdvance).where(
            NatNextGameMarketAdvance.order_id.in_(ids),
        ))).all()
        funding = {row.order_id: row for row in rows}
        return [{**payload, "advance_paid": funding[payload["id"]].advance_paid if payload["id"] in funding else 0,
                 "outstanding_amount": funding[payload["id"]].outstanding_amount if payload["id"] in funding else 0,
                 "advance_locked": payload["id"] in funding and funding[payload["id"]].outstanding_amount > 1e-8}
                for payload in payloads]


__all__ = ["NextGameAdvanceService"]
