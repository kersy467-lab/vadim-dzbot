"""Commodity browser data sourced exclusively from the next-game economy."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameFacility, NatNextGameInventory,
    NatNextGameMarketOrder, NatNextGameMarketTrade,
)
from backend.natbirzha.next_game_catalog import RECIPES, get_next_game_items
from backend.natbirzha.services.next_game_market_read_service import NextGameMarketReadService
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_service.common import BUY_MARKUP, SELL_MARKDOWN
from backend.natbirzha.services.next_game_advance_service import NextGameAdvanceService


def _iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


class NextGameMarketBrowserService:
    @classmethod
    async def catalog(cls, session, owner_tg_id):
        company = await NextGameService._owned_company(session, owner_tg_id)
        facilities = (await session.scalars(select(NatNextGameFacility).where(
            NatNextGameFacility.company_id == company.id,
        ))).all()
        branches = set(company.branch_path or []) | {row.branch_id for row in facilities}
        outputs = {RECIPES[branch][0] for branch in branches if branch in RECIPES}
        inputs = {item for row in facilities if row.branch_id in RECIPES
                  for item in RECIPES[row.branch_id][2]}
        inventory = (await session.scalars(select(NatNextGameInventory).where(
            NatNextGameInventory.company_id == company.id,
        ))).all()
        return {
            "items": [{"id": item_id, **item, "isIndustry": item_id in outputs}
                      for item_id, item in get_next_game_items().items()],
            "input_ids": sorted(inputs),
            "inventory": {row.item_id: round(row.quantity, 4) for row in inventory},
            "company_id": company.id, "cash": round(company.cash, 2),
        }

    @staticmethod
    def execution_query():
        buyer, seller = aliased(NatNextGameCompany), aliased(NatNextGameCompany)
        return select(NatNextGameMarketTrade).join(
            buyer, buyer.id == NatNextGameMarketTrade.buyer_company_id,
        ).join(seller, seller.id == NatNextGameMarketTrade.seller_company_id).where(
            buyer.owner_tg_id != seller.owner_tg_id,
        )

    @classmethod
    async def item(cls, session, owner_tg_id, item_id):
        metadata = get_next_game_items().get(item_id)
        if metadata is None:
            raise ValueError("Такого товара нет в рынке 2.0")
        company = await NextGameService._owned_company(session, owner_tg_id)
        inventory = await NextGameService._inventory_row(session, company.id, item_id)
        treasury = await NextGameService._treasury(session)
        orders = await NextGameMarketReadService.open_orders(session, item_ids={item_id})
        own_rows = (await session.scalars(select(NatNextGameMarketOrder).where(
            NatNextGameMarketOrder.company_id == company.id,
            NatNextGameMarketOrder.item_id == item_id,
        ).order_by(NatNextGameMarketOrder.id.desc()).limit(100))).all()
        trades = (await session.scalars(cls.execution_query().where(
            NatNextGameMarketTrade.item_id == item_id,
        ).order_by(NatNextGameMarketTrade.executed_at.desc(),
                   NatNextGameMarketTrade.id.desc()).limit(200))).all()
        # Reference uses actual executions, never limit orders or NPC corridor.
        history = [{"id": row.id, "price": row.price, "quantity": row.quantity,
                    "timestamp": _iso(row.executed_at)} for row in reversed(trades)]
        base = float(metadata["base_price"])
        from backend.natbirzha.services.next_game_npc_policy import remaining_buyback
        return {
            "item": {"id": item_id, **metadata},
            "inventory_quantity": round(inventory.quantity if inventory else 0, 4),
            "cash": round(company.cash, 2),
            "bids": [row for row in orders if row["side"] == "BUY"],
            "asks": [row for row in orders if row["side"] == "SELL"],
            "history": history,
            "user_orders": await NextGameAdvanceService.decorate_orders(session, [
                NextGameMarketReadService.order_payload(row, company.name) for row in own_rows]),
            "reference_price": round(trades[0].price, 4) if trades else None,
            "advance_reference_price": await NextGameAdvanceService.reference(session, item_id, company.id),
            "npc": {"buy_price": round(base * BUY_MARKUP, 2),
                    "sell_price": round(base * SELL_MARKDOWN, 2),
                    "buyback_remaining_cash": await remaining_buyback(session, company.id, item_id),
                    "unlimited_purchase": True,
                    "treasury_cash": await NextGameService._available_treasury_cash(session, treasury),
                    "treasury_quantity": float((treasury.inventory_json or {}).get(item_id, 0))},
        }

    @classmethod
    async def liquidity(cls, session, *, now=None):
        current = now or datetime.now(timezone.utc).replace(tzinfo=None)
        buyer, seller = aliased(NatNextGameCompany), aliased(NatNextGameCompany)
        trade = NatNextGameMarketTrade
        turnover = func.sum(trade.quantity * trade.price)
        rows = (await session.execute(select(
            trade.item_id, func.sum(trade.quantity), func.count(trade.id), turnover,
        ).join(buyer, buyer.id == trade.buyer_company_id).join(
            seller, seller.id == trade.seller_company_id,
        ).where(buyer.owner_tg_id != seller.owner_tg_id,
                trade.executed_at >= current - timedelta(hours=24),
                trade.executed_at <= current).group_by(trade.item_id)
            .order_by(turnover.desc(), trade.item_id))).all()
        catalog = get_next_game_items()
        return {"items": [{"item_id": item_id,
                           "name": catalog.get(item_id, {}).get("name", item_id),
                           "unit": catalog.get(item_id, {}).get("unit", "шт."),
                           "quantity": round(quantity, 4), "sale_count": count,
                           "buyer_cash_paid": round(cash, 8)}
                          for item_id, quantity, count, cash in rows],
                "refreshed_at": _iso(current)}
