"""Read-only market book, own-order and execution-history views."""

from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import (
    NatNextGameCompany,
    NatNextGameMarketOrder,
    NatNextGameMarketTrade,
)
from backend.natbirzha.next_game_catalog import get_next_game_items
from backend.natbirzha.services.next_game_service import NextGameService


class NextGameMarketReadService:
    @classmethod
    async def list_market(
        cls, session: AsyncSession, *, item_id: str | None = None
    ) -> dict[str, Any]:
        item_ids = None
        if item_id is not None:
            if item_id not in get_next_game_items():
                raise ValueError("Такого товара нет в рынке 2.0")
            item_ids = {item_id}
        return {
            "open_orders": await cls.open_orders(session, item_ids=item_ids),
            "trades": await cls.trade_history(session, item_ids=item_ids),
        }

    @classmethod
    async def list_my_orders(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        *,
        item_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if item_id is not None and item_id not in get_next_game_items():
            raise ValueError("Такого товара нет в рынке 2.0")
        company = await NextGameService._owned_company(session, owner_tg_id)
        return await cls.open_orders(
            session, item_ids={item_id} if item_id else None, company_id=company.id,
        )

    @classmethod
    async def market_snapshot(
        cls,
        session: AsyncSession,
        *,
        company_id: int,
        item_ids: Iterable[str],
    ) -> dict[str, Any]:
        relevant = set(item_ids)
        return {
            "open_orders": await cls.open_orders(session, item_ids=relevant),
            "my_orders": await cls.open_orders(
                session, item_ids=relevant, company_id=company_id,
            ),
            "trades": await cls.trade_history(session, item_ids=relevant),
        }

    @classmethod
    async def open_orders(
        cls,
        session: AsyncSession,
        *,
        item_ids: set[str] | None = None,
        company_id: int | None = None,
    ) -> list[dict[str, Any]]:
        query = select(NatNextGameMarketOrder, NatNextGameCompany.name).join(
            NatNextGameCompany, NatNextGameCompany.id == NatNextGameMarketOrder.company_id,
        ).where(
            NatNextGameMarketOrder.status == "OPEN",
            NatNextGameMarketOrder.remaining_quantity > 0,
        )
        if item_ids is not None:
            if not item_ids:
                return []
            query = query.where(NatNextGameMarketOrder.item_id.in_(item_ids))
        if company_id is not None:
            query = query.where(NatNextGameMarketOrder.company_id == company_id)
        rows = (await session.execute(query)).all()
        payloads = [cls.order_payload(order, company_name) for order, company_name in rows]
        payloads.sort(key=lambda row: (
            row["item_id"], 0 if row["side"] == "BUY" else 1,
            -row["limit_price"] if row["side"] == "BUY" else row["limit_price"],
            row["id"],
        ))
        return payloads

    @classmethod
    async def trade_history(
        cls, session: AsyncSession, *, item_ids: set[str] | None = None
    ) -> list[dict[str, Any]]:
        if item_ids is not None and not item_ids:
            return []
        buyer = aliased(NatNextGameCompany)
        seller = aliased(NatNextGameCompany)
        query = select(NatNextGameMarketTrade, buyer.name, seller.name).join(
            buyer, buyer.id == NatNextGameMarketTrade.buyer_company_id,
        ).join(
            seller, seller.id == NatNextGameMarketTrade.seller_company_id,
        )
        if item_ids is not None:
            query = query.where(NatNextGameMarketTrade.item_id.in_(item_ids))
        rows = (await session.execute(
            query.order_by(NatNextGameMarketTrade.executed_at.desc(), NatNextGameMarketTrade.id.desc())
            .limit(24)
        )).all()
        return [
            cls.trade_payload(trade, buyer_name, seller_name)
            for trade, buyer_name, seller_name in rows
        ]

    @staticmethod
    def order_payload(order: NatNextGameMarketOrder, company_name: str) -> dict[str, Any]:
        return {
            "id": int(order.id),
            "company_id": int(order.company_id),
            "company_name": str(company_name),
            "item_id": str(order.item_id),
            "side": str(order.side),
            "limit_price": round(float(order.limit_price), 4),
            "quantity": round(float(order.quantity), 4),
            "remaining_quantity": round(float(order.remaining_quantity), 4),
            "reserved_cash": round(float(order.reserved_cash), 8),
            "status": str(order.status),
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }

    @staticmethod
    def trade_payload(
        trade: NatNextGameMarketTrade,
        buyer_name: str,
        seller_name: str,
    ) -> dict[str, Any]:
        item = get_next_game_items().get(trade.item_id, {})
        return {
            "id": int(trade.id) if trade.id is not None else None,
            "buy_order_id": int(trade.buy_order_id),
            "sell_order_id": int(trade.sell_order_id),
            "buyer_company_id": int(trade.buyer_company_id),
            "seller_company_id": int(trade.seller_company_id),
            "buyer_name": str(buyer_name),
            "seller_name": str(seller_name),
            "item_id": str(trade.item_id),
            "item_name": item.get("name", str(trade.item_id)),
            "quantity": round(float(trade.quantity), 4),
            "price": round(float(trade.price), 4),
            "executed_at": trade.executed_at.isoformat() if trade.executed_at else None,
        }


__all__ = ["NextGameMarketReadService"]
