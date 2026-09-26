from datetime import datetime
from decimal import Decimal
from math import isfinite
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.natbirzha.config import get_game_now, get_game_today, normalize_dt, nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, CANONICAL_ITEMS
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.inventory_capacity_service import InventoryCapacityService
from backend.natbirzha.services.market_settlement import cancel_market_order, money, remaining_buy_escrow

MARKET_QUANTITY_DECIMALS = 6


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
                NatMarketOrder.remaining_qty > 0
            )
            .order_by(NatMarketOrder.price.desc(), NatMarketOrder.created_at.asc())
            .limit(20)
        )
        bids = [
            {"id": o.id, "price": o.price, "remaining_qty": o.remaining_qty, "company_id": o.company_id}
            for o in bids_res.scalars().all()
        ]

        asks_res = await session.execute(
            select(NatMarketOrder)
            .where(
                NatMarketOrder.item_id == item_id,
                NatMarketOrder.order_type == "SELL",
                NatMarketOrder.status == "ACTIVE",
                NatMarketOrder.remaining_qty > 0
            )
            .order_by(NatMarketOrder.price.asc(), NatMarketOrder.created_at.asc())
            .limit(20)
        )
        asks = [
            {"id": o.id, "price": o.price, "remaining_qty": o.remaining_qty, "company_id": o.company_id}
            for o in asks_res.scalars().all()
        ]

        trades_res = await session.execute(
            select(NatMarketTrade)
            .where(NatMarketTrade.item_id == item_id)
            .order_by(NatMarketTrade.executed_at.desc(), NatMarketTrade.id.desc())
            .limit(48)
        )
        history = [
            {"timestamp": trade.executed_at.isoformat(), "price": trade.price}
            for trade in reversed(trades_res.scalars().all())
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
                }
                for order in orders_res.scalars().all()
            ]

        return {
            "item_id": item_id,
            "bids": bids,
            "asks": asks,
            "history": history,
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
        commit: bool = True
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

        # Check active State market restrictions (§28)
        from backend.natbirzha.services.creator_service import CreatorService
        allowed, restr_err = await CreatorService.check_market_restriction(session, company.id, item_id, price)
        if not allowed:
            raise ValueError(restr_err)

        now = get_game_now()
        locked_company = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        company = locked_company or company

        if order_type == "BUY":
            total_cost = money(Decimal(str(price)) * Decimal(str(quantity)))
            if company.cash < total_cost:
                raise ValueError(f"Insufficient cash. Required: {total_cost}, Available: {company.cash}")
            company.cash = float(money(Decimal(str(company.cash)) - total_cost))
        elif order_type == "SELL":
            inv_res = await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == company.id,
                    NatInventory.item_id == item_id
                ).with_for_update()
            )
            inv = inv_res.scalar_one_or_none()
            if not inv or inv.available_quantity < quantity:
                avail = inv.available_quantity if inv else 0.0
                raise ValueError(f"Insufficient inventory to sell. Required: {quantity}, Available: {avail}")
            inv.reserved_quantity += quantity

        order = NatMarketOrder(
            company_id=company.id,
            order_type=order_type,
            item_id=item_id,
            price=price,
            quantity=quantity,
            remaining_qty=quantity,
            status="ACTIVE",
            created_at=now
        )
        session.add(order)
        await session.flush()

        # Trigger immediate matching against opposite book
        await cls.match_orders_for_item(session, item_id)
        await session.flush()
        if commit:
            await session.commit()
            await session.refresh(order)
        return order

    @classmethod
    async def match_orders_for_item(cls, session: AsyncSession, item_id: str) -> int:
        trades_count = 0
        now = get_game_now()

        while True:
            # Walk bids in priority order until one has an executable ask.
            buy_res = await session.execute(
                select(NatMarketOrder)
                .where(
                    NatMarketOrder.item_id == item_id,
                    NatMarketOrder.order_type == "BUY",
                    NatMarketOrder.status == "ACTIVE",
                    NatMarketOrder.remaining_qty > 0
                )
                .order_by(NatMarketOrder.price.desc(), NatMarketOrder.created_at.asc())
                .with_for_update(skip_locked=True)
            )
            buy_orders = buy_res.scalars().all()
            if not buy_orders:
                break

            buy_order = None
            sell_order = None
            for candidate_buy in buy_orders:
                # Self-trade exclusion is per pair. A blocked top bid must not
                # prevent a lower bid from trading against that company's ask.
                sell_res = await session.execute(
                    select(NatMarketOrder)
                    .where(
                        NatMarketOrder.item_id == item_id,
                        NatMarketOrder.order_type == "SELL",
                        NatMarketOrder.status == "ACTIVE",
                        NatMarketOrder.remaining_qty > 0,
                        NatMarketOrder.company_id != candidate_buy.company_id,
                    )
                    .order_by(NatMarketOrder.price.asc(), NatMarketOrder.created_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                candidate_sell = sell_res.scalar_one_or_none()
                if candidate_sell and candidate_buy.price >= candidate_sell.price:
                    buy_order = candidate_buy
                    sell_order = candidate_sell
                    break

            if not buy_order or not sell_order:
                break

            # Determine execution price (maker price: earlier order's price)
            maker_is_sell = normalize_dt(sell_order.created_at) <= normalize_dt(buy_order.created_at)
            trade_price = sell_order.price if maker_is_sell else buy_order.price
            invalid_order = next((order for order in (buy_order, sell_order)
                                  if abs(order.remaining_qty - round(order.remaining_qty, MARKET_QUANTITY_DECIMALS)) > 1e-9), None)
            if invalid_order:
                invalid_company = (await session.execute(
                    select(NatCompany).where(NatCompany.id == invalid_order.company_id).with_for_update()
                )).scalar_one_or_none()
                if invalid_company:
                    await cls.cancel_order(session, invalid_company, invalid_order.id, commit=False)
                else:
                    invalid_order.status = "CANCELLED"
                    invalid_order.closed_at = now
                await session.flush()
                continue
            trade_qty = round(min(buy_order.remaining_qty, sell_order.remaining_qty), MARKET_QUANTITY_DECIMALS)
            available_escrow = await remaining_buy_escrow(session, buy_order)
            total_amount = min(money(Decimal(str(trade_price)) * Decimal(str(trade_qty))), available_escrow)
            price_diff = min(
                money(max(Decimal(0), Decimal(str(buy_order.price)) - Decimal(str(trade_price))) * Decimal(str(trade_qty))),
                max(Decimal(0), available_escrow - total_amount),
            )
            fee = min(money(total_amount * Decimal("0.01")), total_amount)

            buyer_comp = (await session.execute(
                select(NatCompany).where(NatCompany.id == buy_order.company_id).with_for_update()
            )).scalar_one_or_none()
            seller_comp = (await session.execute(
                select(NatCompany).where(NatCompany.id == sell_order.company_id).with_for_update()
            )).scalar_one_or_none()
            if not buyer_comp or not seller_comp:
                break

            # Validate and lock reserved seller inventory before moving any money.
            seller_inv = (await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == seller_comp.id,
                    NatInventory.item_id == item_id
                ).with_for_update()
            )).scalar_one_or_none()
            if not seller_inv or seller_inv.reserved_quantity < trade_qty or seller_inv.quantity < trade_qty:
                sell_order.status = "CANCELLED"
                sell_order.closed_at = now
                if seller_inv:
                    seller_inv.reserved_quantity = max(0.0, seller_inv.reserved_quantity - sell_order.remaining_qty)
                await session.flush()
                continue
            seller_cogs = round(
                trade_qty * max(0.0, float(seller_inv.avg_cost_basis or 0.0)), 6
            )

            buyer_inv = (await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == buyer_comp.id,
                    NatInventory.item_id == item_id
                ).with_for_update()
            )).scalar_one_or_none()

            # Never let exchange settlement bypass the authoritative inventory cap.
            buyer_qty = buyer_inv.quantity if buyer_inv else 0.0
            cap = await InventoryCapacityService.for_item(session, buyer_comp, item_id)
            if buyer_qty + trade_qty > cap:
                refund = await remaining_buy_escrow(session, buy_order)
                buyer_comp.cash = float(money(Decimal(str(buyer_comp.cash)) + refund))
                buy_order.status = "CANCELLED"
                buy_order.closed_at = now
                await session.flush()
                continue

            if price_diff > 0:
                buyer_comp.cash = float(money(Decimal(str(buyer_comp.cash)) + price_diff))
            seller_proceeds = total_amount - fee
            dividend_withheld = await DividendService.accrue_cash_inflow(
                session, seller_comp, float(seller_proceeds), now=now
            )
            seller_comp.cash = float(money(Decimal(str(seller_comp.cash)) + seller_proceeds - Decimal(str(dividend_withheld))))
            await CompanyProfitLedgerService.record(
                session,
                seller_comp.id,
                now,
                revenue=float(total_amount),
                cost_of_goods_sold=seller_cogs,
                other_expenses=float(fee),
            )

            seller_inv.quantity = round(max(0.0, seller_inv.quantity - trade_qty), MARKET_QUANTITY_DECIMALS)
            seller_inv.reserved_quantity = round(max(0.0, seller_inv.reserved_quantity - trade_qty), MARKET_QUANTITY_DECIMALS)

            if not buyer_inv:
                buyer_inv = NatInventory(
                    company_id=buyer_comp.id,
                    item_id=item_id,
                    quantity=round(trade_qty, MARKET_QUANTITY_DECIMALS),
                    reserved_quantity=0.0,
                    avg_cost_basis=trade_price
                )
                session.add(buyer_inv)
            else:
                old_qty = buyer_inv.quantity
                new_qty = round(old_qty + trade_qty, MARKET_QUANTITY_DECIMALS)
                if new_qty > 0:
                    buyer_inv.avg_cost_basis = round(
                        ((old_qty * buyer_inv.avg_cost_basis) + float(total_amount)) / new_qty, 4
                    )
                buyer_inv.quantity = new_qty

            # Update orders
            buy_order.remaining_qty = round(max(0.0, buy_order.remaining_qty - trade_qty), MARKET_QUANTITY_DECIMALS)
            if buy_order.remaining_qty <= 0:
                buy_order.status = "FILLED"
                buy_order.closed_at = now
                buyer_comp.cash = float(money(
                    Decimal(str(buyer_comp.cash)) + max(Decimal(0), available_escrow - total_amount - price_diff)
                ))

            sell_order.remaining_qty = round(max(0.0, sell_order.remaining_qty - trade_qty), MARKET_QUANTITY_DECIMALS)
            if sell_order.remaining_qty <= 0:
                sell_order.status = "FILLED"
                sell_order.closed_at = now

            trade = NatMarketTrade(
                buy_order_id=buy_order.id,
                sell_order_id=sell_order.id,
                buyer_company_id=buyer_comp.id,
                seller_company_id=seller_comp.id,
                item_id=item_id,
                price=trade_price,
                quantity=trade_qty,
                total_amount=float(total_amount),
                fee_amount=float(fee),
                executed_at=now
            )
            session.add(trade)

            # Update daily financials for buyer (opex) and seller (revenue)
            today = get_game_today()
            for comp_id, rev_delta, opex_delta in [
                (buyer_comp.id, 0.0, float(total_amount)),
                (seller_comp.id, float(seller_proceeds), 0.0)
            ]:
                f_res = await session.execute(
                    select(NatDailyFinancials).where(
                        NatDailyFinancials.company_id == comp_id,
                        NatDailyFinancials.calendar_date == today
                    )
                )
                fin = f_res.scalar_one_or_none()
                if not fin:
                    fin = NatDailyFinancials(
                        company_id=comp_id,
                        calendar_date=today,
                        gross_revenue=rev_delta,
                        opex=opex_delta,
                        closed_profit=round(rev_delta - opex_delta, 2),
                        developer_fee_paid=0.0
                    )
                    session.add(fin)
                else:
                    fin.gross_revenue += rev_delta
                    fin.opex += opex_delta
                    fin.closed_profit = round(fin.gross_revenue - fin.opex, 2)

            trades_count += 1
            await session.flush()

        return trades_count

    @classmethod
    async def cancel_order(cls, session: AsyncSession, company: NatCompany, order_id: int, commit: bool = True) -> bool:
        return await cancel_market_order(session, company, order_id, commit=commit)
