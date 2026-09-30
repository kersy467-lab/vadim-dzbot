from decimal import Decimal
from math import isfinite
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, CANONICAL_ITEMS
from backend.natbirzha.models.market import NatMarketOrder
from backend.natbirzha.services.market_advance_service import MarketAdvanceService
from backend.natbirzha.services.market_matching_service import MarketMatchingService, MARKET_QUANTITY_DECIMALS
from backend.natbirzha.services.market_settlement import cancel_market_order, money


class MarketService:
    @staticmethod
    async def get_orderbook(
        session: AsyncSession, item_id: str, company_id: Optional[int] = None
    ) -> Dict[str, Any]:
        if item_id not in CANONICAL_ITEMS:
            raise ValueError(f"Unknown item: {item_id}")

        bids_res = await session.execute(
            select(NatMarketOrder)
            .where(
                NatMarketOrder.item_id == item_id,
                NatMarketOrder.order_type == "BUY",
                NatMarketOrder.status == "ACTIVE",
                NatMarketOrder.remaining_qty > 0,
            )
            .order_by(NatMarketOrder.price.desc(), NatMarketOrder.created_at.asc())
            .limit(20)
        )
        bids = [
            {"id": row.id, "price": row.price, "remaining_qty": row.remaining_qty, "company_id": row.company_id}
            for row in bids_res.scalars().all()
        ]
        asks_res = await session.execute(
            select(NatMarketOrder)
            .where(
                NatMarketOrder.item_id == item_id,
                NatMarketOrder.order_type == "SELL",
                NatMarketOrder.status == "ACTIVE",
                NatMarketOrder.remaining_qty > 0,
            )
            .order_by(NatMarketOrder.price.asc(), NatMarketOrder.created_at.asc())
            .limit(20)
        )
        asks = [
            {"id": row.id, "price": row.price, "remaining_qty": row.remaining_qty, "company_id": row.company_id}
            for row in asks_res.scalars().all()
        ]
        trades = await MarketAdvanceService.external_trade_history(session, item_id)
        advance_reference_price = MarketAdvanceService.reference_price_from_history(
            trades, now=get_game_now()
        )
        history = [
            {"timestamp": trade.executed_at.isoformat(), "price": trade.price}
            for trade in reversed(trades)
        ]

        user_orders = []
        if company_id is not None:
            orders_res = await session.execute(
                select(NatMarketOrder)
                .where(
                    NatMarketOrder.item_id == item_id,
                    NatMarketOrder.company_id == company_id,
                    NatMarketOrder.status == "ACTIVE",
                    NatMarketOrder.remaining_qty > 0,
                )
                .order_by(NatMarketOrder.created_at.asc(), NatMarketOrder.id.asc())
            )
            user_orders = [
                {
                    "id": order.id,
                    "order_type": order.order_type,
                    "price": order.price,
                    "remaining_quantity": order.remaining_qty,
                    "state_advance_amount": order.state_advance_amount,
                    "state_advance_remaining_amount": order.state_advance_remaining_amount,
                    "state_advance_remaining_quantity": order.state_advance_remaining_quantity,
                    "state_advance_reference_price": order.state_advance_reference_price,
                    "state_advance_reason": order.state_advance_reason,
                    "can_cancel": order.state_advance_remaining_quantity <= 1e-9,
                }
                for order in orders_res.scalars().all()
            ]
        return {
            "item_id": item_id,
            "bids": bids,
            "asks": asks,
            "history": history,
            "advance_reference_price": advance_reference_price,
            "user_orders": user_orders,
        }

    @classmethod
    async def create_order(
        cls,
        session: AsyncSession,
        company: NatCompany,
        order_type: str,
        item_id: str,
        price: float,
        quantity: float,
        commit: bool = True,
    ) -> NatMarketOrder:
        order_type = order_type.upper()
        if order_type not in ("BUY", "SELL"):
            raise ValueError("Invalid order type: must be BUY or SELL.")
        if item_id not in CANONICAL_ITEMS:
            raise ValueError(f"Unknown item: {item_id}")
        if not isfinite(float(price)) or not isfinite(float(quantity)) or price <= 0 or quantity <= 0:
            raise ValueError("Price and quantity must be positive.")
        rounded_quantity = round(float(quantity), MARKET_QUANTITY_DECIMALS)
        if abs(float(quantity) - rounded_quantity) > 1e-9:
            raise ValueError("Quantity must use increments of 0.000001.")
        quantity = rounded_quantity

        from backend.natbirzha.services.creator_service import CreatorService
        allowed, restriction_error = await CreatorService.check_market_restriction(
            session, company.id, item_id, price
        )
        if not allowed:
            raise ValueError(restriction_error)

        now = get_game_now()
        reference_price = (
            await MarketAdvanceService.reference_price(session, item_id, now=now)
            if order_type == "SELL" else None
        )
        eligible = bool(
            order_type == "SELL"
            and reference_price is not None
            and float(price) <= reference_price + 1e-9
        )
        treasury = await MarketAdvanceService.treasury_for_order(
            session, item_id, eligible_to_advance=eligible
        )

        locked_company = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        company = locked_company or company

        if order_type == "BUY":
            total_cost = money(Decimal(str(price)) * Decimal(str(quantity)))
            if company.cash < total_cost:
                raise ValueError(f"Insufficient cash. Required: {total_cost}, Available: {company.cash}")
            company.cash = float(money(Decimal(str(company.cash)) - total_cost))
        else:
            inventory = (await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == company.id,
                    NatInventory.item_id == item_id,
                ).with_for_update()
            )).scalar_one_or_none()
            if not inventory or inventory.available_quantity < quantity:
                available = inventory.available_quantity if inventory else 0.0
                raise ValueError(f"Insufficient inventory to sell. Required: {quantity}, Available: {available}")
            inventory.reserved_quantity += quantity

        order = NatMarketOrder(
            company_id=company.id,
            order_type=order_type,
            item_id=item_id,
            price=price,
            quantity=quantity,
            remaining_qty=quantity,
            status="ACTIVE",
            created_at=now,
        )
        session.add(order)
        await session.flush()
        if order_type == "SELL":
            await MarketAdvanceService.fund_sell_order(
                session, company, inventory, order, treasury, reference_price, now=now
            )
        await session.flush()

        await MarketMatchingService.match_orders_for_item(session, item_id)
        await session.flush()
        if commit:
            await session.commit()
            await session.refresh(order)
        return order

    @classmethod
    async def match_orders_for_item(cls, session: AsyncSession, item_id: str) -> int:
        return await MarketMatchingService.match_orders_for_item(session, item_id)

    @classmethod
    async def cancel_order(
        cls, session: AsyncSession, company: NatCompany, order_id: int, commit: bool = True
    ) -> bool:
        return await cancel_market_order(session, company, order_id, commit=commit)


__all__ = ["MarketService", "MARKET_QUANTITY_DECIMALS"]
