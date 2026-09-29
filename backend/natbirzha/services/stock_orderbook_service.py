"""Real two-sided order book and trade matching for public company shares."""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import (
    NatStock,
    NatStockHolding,
    NatStockOrder,
    NatStockPriceSnapshot,
    NatStockTrade,
)


class StockOrderbookService:
    MAX_LEVELS = 12
    PRICE_BAND_PCT = 0.35
    FAIR_PRICE_MIN_PCT = 0.75
    FAIR_PRICE_MAX_PCT = 1.25
    REFERENCE_WINDOW = timedelta(hours=24)
    REFERENCE_TRADE_LIMIT = 48
    MIN_REFERENCE_TRADES = 3
    MAX_TRADE_IMPACT_PCT = 0.05

    @staticmethod
    def _is_ipo_order(stock: NatStock, order: NatStockOrder) -> bool:
        if order.trader_company_id != stock.company_id or not stock.ipo_date:
            return False
        return abs((order.created_at - stock.ipo_date).total_seconds()) <= 2

    @staticmethod
    def _same_owner(buyer: NatCompany, seller: NatCompany) -> bool:
        buyer_user_id = getattr(buyer, "user_id", None)
        seller_user_id = getattr(seller, "user_id", None)
        return (
            buyer_user_id is not None
            and seller_user_id is not None
            and int(buyer_user_id) == int(seller_user_id)
        )

    @staticmethod
    def _fair_price(stock: NatStock) -> float:
        total_shares = max(1, int(stock.total_shares or 1))
        valuation = max(0.0, float(stock.last_valuation or 0.0))
        if valuation > 0:
            return max(0.01, valuation / total_shares)
        return max(0.01, float(stock.current_price or 0.01))

    @classmethod
    def _safe_reference_price(cls, stock: NatStock) -> float:
        """Keep the order corridor anchored to audited value, not a single last trade."""
        fair = cls._fair_price(stock)
        lower = fair * cls.FAIR_PRICE_MIN_PCT
        upper = fair * cls.FAIR_PRICE_MAX_PCT
        current = max(0.01, float(stock.current_price or fair))
        return round(max(lower, min(upper, current)), 2)

    @classmethod
    def _price_bounds(cls, stock: NatStock) -> tuple[float, float]:
        anchor = cls._safe_reference_price(stock)
        return (
            round(anchor * (1.0 - cls.PRICE_BAND_PCT), 2),
            round(anchor * (1.0 + cls.PRICE_BAND_PCT), 2),
        )

    @classmethod
    def _price_is_valid(cls, stock: NatStock, price: float) -> bool:
        lower, upper = cls._price_bounds(stock)
        value = float(price)
        return lower - 1e-9 <= value <= upper + 1e-9

    @staticmethod
    async def _holding(session: AsyncSession, stock_id: int, company_id: int, lock: bool = False):
        stmt = select(NatStockHolding).where(
            NatStockHolding.stock_id == stock_id,
            NatStockHolding.holder_company_id == company_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        return await session.scalar(stmt)

    @classmethod
    async def reference_price(
        cls, session: AsyncSession, stock_id: int, *, now: datetime | None = None
    ) -> float | None:
        """Return a median quote only after several external trades from distinct owner pairs."""
        current = now or get_game_now()
        history = (await session.execute(
            select(NatStockTrade)
            .where(
                NatStockTrade.stock_id == stock_id,
                NatStockTrade.executed_at >= current - cls.REFERENCE_WINDOW,
                NatStockTrade.buyer_user_id != NatStockTrade.seller_user_id,
                NatStockTrade.price > 0,
                NatStockTrade.shares_count > 0,
            )
            .order_by(NatStockTrade.executed_at.desc(), NatStockTrade.id.desc())
            .limit(cls.REFERENCE_TRADE_LIMIT)
        )).scalars().all()
        counterparties = {
            tuple(sorted((int(row.buyer_user_id), int(row.seller_user_id))))
            for row in history
        }
        if len(history) < cls.MIN_REFERENCE_TRADES or len(counterparties) < 2:
            return None
        return round(float(median(float(row.price) for row in history)), 2)

    @classmethod
    async def orderbook(
        cls, session: AsyncSession, stock_id: int, company_id: int | None = None
    ) -> dict[str, Any]:
        stock = await session.get(NatStock, stock_id)
        if not stock or not stock.is_listed:
            raise ValueError("Stock is not actively listed.")
        rows = (await session.execute(
            select(NatStockOrder).where(
                NatStockOrder.stock_id == stock_id,
                NatStockOrder.status == "ACTIVE",
                NatStockOrder.remaining_shares > 0,
            ).order_by(NatStockOrder.created_at.asc(), NatStockOrder.id.asc())
        )).scalars().all()
        anchor = cls._safe_reference_price(stock)
        valid_rows = [row for row in rows if cls._price_is_valid(stock, row.price)]

        def aggregate(side: str) -> list[dict[str, Any]]:
            levels: dict[float, int] = {}
            for row in valid_rows:
                if row.order_type != side:
                    continue
                price = round(float(row.price), 2)
                levels[price] = levels.get(price, 0) + int(row.remaining_shares)
            prices = sorted(levels, reverse=side == "BUY")[: cls.MAX_LEVELS]
            return [{"price": price, "quantity": levels[price]} for price in prices]

        own_orders = []
        if company_id is not None:
            own_orders = [{
                "order_id": row.id,
                "side": row.order_type,
                "price": row.price,
                "quantity": row.shares_count,
                "remaining": row.remaining_shares,
                "out_of_band": not cls._price_is_valid(stock, row.price),
            } for row in rows if row.trader_company_id == company_id and not cls._is_ipo_order(stock, row)]
        bids, asks = aggregate("BUY"), aggregate("SELL")
        lower, upper = cls._price_bounds(stock)
        return {
            "stock_id": stock.id,
            "current_price": anchor,
            "reference_price": anchor,
            "price_band": {"min": lower, "max": upper},
            "best_bid": bids[0]["price"] if bids else None,
            "best_ask": asks[0]["price"] if asks else None,
            "bids": bids,
            "asks": asks,
            "own_orders": own_orders,
        }

    @classmethod
    async def market_pressure(cls, session: AsyncSession, stock: NatStock) -> float:
        rows = (await session.execute(select(NatStockOrder).where(
            NatStockOrder.stock_id == stock.id,
            NatStockOrder.status == "ACTIVE",
            NatStockOrder.remaining_shares > 0,
        ))).scalars().all()
        valid_rows = [row for row in rows if cls._price_is_valid(stock, row.price)]
        buy = sum(int(row.remaining_shares) for row in valid_rows if row.order_type == "BUY")
        sell = sum(
            int(row.remaining_shares) for row in valid_rows
            if row.order_type == "SELL" and not cls._is_ipo_order(stock, row)
        )
        total = buy + sell
        return 0.0 if total <= 0 else max(-1.0, min(1.0, (buy - sell) / total))

    @classmethod
    async def _cancel_out_of_band_orders(
        cls, session: AsyncSession, stock: NatStock, anchor: float, now: datetime
    ) -> None:
        orders = (await session.execute(
            select(NatStockOrder).where(
                NatStockOrder.stock_id == stock.id,
                NatStockOrder.status == "ACTIVE",
                NatStockOrder.remaining_shares > 0,
            ).with_for_update()
        )).scalars().all()
        for order in orders:
            if cls._price_is_valid(stock, order.price):
                continue
            if cls._is_ipo_order(stock, order):
                # The unsold original float follows the protected quote.
                order.price = anchor
                continue
            await cls.cancel_order(
                session, order.trader_company_id, order.id, now=now, commit=False
            )

    @classmethod
    async def place_limit_order(
        cls, session: AsyncSession, company_id: int, stock_id: int, side: str,
        quantity: int, price: float, now: datetime | None = None, *, commit: bool = True,
    ) -> dict[str, Any]:
        side = side.upper()
        if side not in ("BUY", "SELL") or quantity <= 0 or price <= 0:
            raise ValueError("Side, quantity and price are invalid.")
        now = now or get_game_now()
        stock = await session.scalar(select(NatStock).where(
            NatStock.id == stock_id, NatStock.is_listed == True
        ).with_for_update())
        company = await session.scalar(select(NatCompany).where(
            NatCompany.id == company_id
        ).with_for_update())
        if not stock or not company:
            raise ValueError("Stock or company not found.")
        if company.is_bankrupt:
            raise ValueError("Bankrupt companies cannot trade stocks.")
        price = round(float(price), 2)
        anchor = cls._safe_reference_price(stock)
        lower, upper = cls._price_bounds(stock)
        if price < lower or price > upper:
            raise ValueError(
                f"Limit price must be between {lower:.2f} and {upper:.2f} cash."
            )

        # Repair a legacy/manipulated quote before it can authorize new orders.
        if abs(float(stock.current_price or 0.0) - anchor) > 1e-9:
            stock.current_price = anchor
            session.add(NatStockPriceSnapshot(
                stock_id=stock.id,
                price=anchor,
                valuation=round(float(stock.last_valuation or 0.0), 2),
                captured_at=now,
            ))
        await cls._cancel_out_of_band_orders(session, stock, anchor, now)

        if side == "BUY":
            escrow = round(quantity * price, 2)
            if company.cash < escrow:
                raise ValueError("Insufficient cash for the limit order.")
            company.cash = round(company.cash - escrow, 2)
        else:
            holding = await cls._holding(session, stock_id, company_id, lock=True)
            active_sells = (await session.execute(select(NatStockOrder).where(
                NatStockOrder.stock_id == stock_id,
                NatStockOrder.trader_company_id == company_id,
                NatStockOrder.order_type == "SELL",
                NatStockOrder.status == "ACTIVE",
                NatStockOrder.remaining_shares > 0,
            ))).scalars().all()
            reserved = sum(
                int(row.remaining_shares) for row in active_sells
                if not cls._is_ipo_order(stock, row)
            )
            available = int(holding.shares_count if holding else 0) - reserved
            if available < quantity:
                raise ValueError("Insufficient unreserved shares for the sell order.")

        order = NatStockOrder(
            stock_id=stock_id,
            trader_company_id=company_id,
            order_type=side,
            shares_count=quantity,
            remaining_shares=quantity,
            price=price,
            status="ACTIVE",
            created_at=now,
        )
        session.add(order)
        await session.flush()
        trades = await cls._match(session, stock, order, now)
        await session.flush()
        if commit:
            await session.commit()
        return {
            "success": True,
            "order_id": order.id,
            "status": order.status,
            "remaining": order.remaining_shares,
            "trades": trades,
        }

    @classmethod
    async def _match(
        cls, session: AsyncSession, stock: NatStock, taker: NatStockOrder, now: datetime
    ) -> list[dict]:
        opposite = "SELL" if taker.order_type == "BUY" else "BUY"
        price_condition = (
            NatStockOrder.price <= taker.price
            if taker.order_type == "BUY"
            else NatStockOrder.price >= taker.price
        )
        order_by = (
            (NatStockOrder.price.asc(), NatStockOrder.created_at.asc())
            if opposite == "SELL"
            else (NatStockOrder.price.desc(), NatStockOrder.created_at.asc())
        )
        makers = (await session.execute(select(NatStockOrder).where(
            NatStockOrder.stock_id == stock.id,
            NatStockOrder.order_type == opposite,
            NatStockOrder.status == "ACTIVE",
            NatStockOrder.remaining_shares > 0,
            NatStockOrder.trader_company_id != taker.trader_company_id,
            price_condition,
        ).order_by(*order_by).with_for_update())).scalars().all()
        trades = []
        for maker in makers:
            if taker.remaining_shares <= 0:
                break
            if not cls._price_is_valid(stock, taker.price):
                await cls.cancel_order(
                    session, taker.trader_company_id, taker.id, now=now, commit=False
                )
                break
            if not cls._price_is_valid(stock, maker.price):
                if cls._is_ipo_order(stock, maker):
                    maker.price = cls._safe_reference_price(stock)
                else:
                    await cls.cancel_order(
                        session, maker.trader_company_id, maker.id, now=now, commit=False
                    )
                    continue
            # A re-priced IPO maker may no longer cross the taker.
            if (taker.order_type == "BUY" and maker.price > taker.price) or (
                taker.order_type == "SELL" and maker.price < taker.price
            ):
                continue

            qty = min(int(taker.remaining_shares), int(maker.remaining_shares))
            trade_price = round(float(maker.price), 2)
            if not cls._price_is_valid(stock, trade_price):
                continue
            buy_order, sell_order = (
                (taker, maker) if taker.order_type == "BUY" else (maker, taker)
            )
            buyer = await session.scalar(
                select(NatCompany).where(NatCompany.id == buy_order.trader_company_id)
                .with_for_update()
            )
            seller = await session.scalar(
                select(NatCompany).where(NatCompany.id == sell_order.trader_company_id)
                .with_for_update()
            )
            if not buyer or not seller or cls._same_owner(buyer, seller):
                continue
            cost = round(qty * trade_price, 2)
            if not cls._is_ipo_order(stock, sell_order):
                seller_holding = await cls._holding(session, stock.id, seller.id, lock=True)
                if not seller_holding or seller_holding.shares_count < qty:
                    sell_order.status = "CANCELLED"
                    sell_order.remaining_shares = 0
                    continue
                seller_holding.shares_count -= qty
                seller_holding.updated_at = now
            # BUY orders escrow their limit price at placement. Refund price improvement.
            refund = round(qty * max(0.0, float(buy_order.price) - trade_price), 2)
            buyer.cash = round(buyer.cash + refund, 2)
            seller.cash = round(seller.cash + cost, 2)
            await cls._credit_shares(session, stock.id, buyer.id, qty, trade_price, now)
            taker.remaining_shares -= qty
            maker.remaining_shares -= qty
            if maker.remaining_shares <= 0:
                maker.status = "FILLED"
            if taker.remaining_shares <= 0:
                taker.status = "FILLED"
            if cls._is_ipo_order(stock, sell_order):
                stock.float_shares = max(0, int(stock.float_shares) - qty)

            session.add(NatStockTrade(
                stock_id=stock.id,
                buyer_company_id=buyer.id,
                seller_company_id=seller.id,
                buyer_user_id=buyer.user_id,
                seller_user_id=seller.user_id,
                shares_count=qty,
                price=trade_price,
                executed_at=now,
            ))
            await session.flush()
            reference = await cls.reference_price(session, stock.id, now=now)
            if reference is not None:
                fair = cls._fair_price(stock)
                target = max(
                    fair * cls.FAIR_PRICE_MIN_PCT,
                    min(fair * cls.FAIR_PRICE_MAX_PCT, reference),
                )
                current = cls._safe_reference_price(stock)
                total_shares = max(1, int(stock.total_shares or 1))
                impact_pct = min(
                    cls.MAX_TRADE_IMPACT_PCT,
                    (qty / total_shares) * cls.PRICE_BAND_PCT,
                )
                max_move = current * impact_pct
                delta = max(-max_move, min(max_move, target - current))
                quote = current + delta
                stock.current_price = round(max(
                    fair * cls.FAIR_PRICE_MIN_PCT,
                    min(fair * cls.FAIR_PRICE_MAX_PCT, quote),
                ), 2)
            else:
                stock.current_price = cls._safe_reference_price(stock)
            session.add(NatStockPriceSnapshot(
                stock_id=stock.id,
                price=round(float(stock.current_price), 6),
                valuation=round(float(stock.last_valuation or 0.0), 2),
                captured_at=now,
            ))
            trades.append({"quantity": qty, "price": trade_price, "total": cost})
        return trades

    @classmethod
    async def _credit_shares(
        cls, session: AsyncSession, stock_id: int, buyer_id: int,
        quantity: int, price: float, now: datetime
    ) -> None:
        holding = await cls._holding(session, stock_id, buyer_id, lock=True)
        if not holding:
            session.add(NatStockHolding(
                stock_id=stock_id,
                holder_company_id=buyer_id,
                shares_count=quantity,
                avg_price=price,
                updated_at=now,
            ))
            return
        total = holding.shares_count + quantity
        previous_cost = holding.shares_count * holding.avg_price
        holding.avg_price = round((previous_cost + quantity * price) / max(1, total), 2)
        holding.shares_count = total
        holding.updated_at = now

    @classmethod
    async def cancel_order(
        cls, session: AsyncSession, company_id: int, order_id: int,
        now: datetime | None = None, *, commit: bool = True
    ) -> dict[str, Any]:
        now = now or get_game_now()
        order = await session.scalar(
            select(NatStockOrder).where(NatStockOrder.id == order_id).with_for_update()
        )
        if not order or order.status != "ACTIVE" or order.trader_company_id != company_id:
            raise ValueError("Active stock order not found.")
        stock = await session.get(NatStock, order.stock_id)
        if stock and cls._is_ipo_order(stock, order):
            raise ValueError("IPO placement cannot be cancelled from the player order book.")
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if order.order_type == "BUY" and company is not None:
            company.cash = round(company.cash + order.remaining_shares * order.price, 2)
        order.status = "CANCELLED"
        order.remaining_shares = 0
        if commit:
            await session.commit()
        return {"success": True, "order_id": order.id, "status": order.status}


__all__ = ["StockOrderbookService"]
