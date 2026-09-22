"""Immediate-or-cancel player-market procurement used by idle supply automation."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.market import NatMarketOrder
from backend.natbirzha.services.market_service import MarketService


class MarketProcurementService:
    @staticmethod
    async def best_ask_price(
        session: AsyncSession,
        item_id: str,
        *,
        exclude_company_id: int,
    ) -> float | None:
        value = await session.scalar(
            select(NatMarketOrder.price)
            .where(
                NatMarketOrder.item_id == item_id,
                NatMarketOrder.order_type == "SELL",
                NatMarketOrder.status == "ACTIVE",
                NatMarketOrder.remaining_qty > 0,
                NatMarketOrder.company_id != exclude_company_id,
            )
            .order_by(NatMarketOrder.price.asc(), NatMarketOrder.created_at.asc())
            .limit(1)
        )
        return float(value) if value is not None else None

    @classmethod
    async def buy_available(
        cls,
        session: AsyncSession,
        company: NatCompany,
        item_id: str,
        quantity: float,
        *,
        max_unit_price: float | None,
    ) -> dict:
        """Buy what is currently offered, then cancel the unmatched remainder."""
        quantity = round(max(0.0, float(quantity)), 6)
        if quantity <= 0:
            return {"success": True, "item_id": item_id, "requested": 0.0, "purchased": 0.0}

        best_ask = await cls.best_ask_price(
            session, item_id, exclude_company_id=company.id
        )
        if best_ask is None:
            return {"success": False, "item_id": item_id, "requested": quantity, "purchased": 0.0, "reason": "no_asks"}
        ceiling = float(max_unit_price) if max_unit_price is not None else best_ask
        if best_ask > ceiling + 1e-9:
            return {"success": False, "item_id": item_id, "requested": quantity, "purchased": 0.0, "reason": "price_limit"}

        affordable = max(0.0, float(company.cash)) / max(ceiling, 1e-9)
        order_quantity = round(min(quantity, affordable), 6)
        if order_quantity <= 0:
            return {"success": False, "item_id": item_id, "requested": quantity, "purchased": 0.0, "reason": "cash"}

        order = await MarketService.create_order(
            session,
            company,
            "BUY",
            item_id,
            ceiling,
            order_quantity,
            commit=False,
        )
        purchased = round(max(0.0, order_quantity - float(order.remaining_qty)), 6)
        if float(order.remaining_qty) > 1e-9:
            await MarketService.cancel_order(session, company, order.id, commit=False)
        return {
            "success": purchased > 0,
            "item_id": item_id,
            "requested": quantity,
            "purchased": purchased,
            "reason": None if purchased > 0 else "no_fill",
        }


__all__ = ["MarketProcurementService"]
