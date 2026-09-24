from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from backend.natbirzha.config import get_game_now, get_game_today, normalize_dt, nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, CANONICAL_ITEMS
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.services.dividend_service import DividendService

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
        if price <= 0 or quantity <= 0:
            raise ValueError("Price and quantity must be positive.")

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
            total_cost = round(price * quantity, 2)
            if company.cash < total_cost:
                raise ValueError(f"Insufficient cash. Required: {total_cost}, Available: {company.cash}")
            company.cash -= total_cost
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
            trade_qty = min(buy_order.remaining_qty, sell_order.remaining_qty)
            total_amount = round(trade_price * trade_qty, 2)
            fee = round(total_amount * 0.01, 2)  # 1% exchange fee

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

            buyer_inv = (await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == buyer_comp.id,
                    NatInventory.item_id == item_id
                ).with_for_update()
            )).scalar_one_or_none()

            # Never let exchange settlement bypass the authoritative inventory cap.
            buyer_qty = buyer_inv.quantity if buyer_inv else 0.0
            cap = float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM)
            if buyer_qty + trade_qty > cap:
                refund = round(buy_order.price * buy_order.remaining_qty, 2)
                buyer_comp.cash = round(buyer_comp.cash + refund, 2)
                buy_order.status = "CANCELLED"
                buy_order.closed_at = now
                await session.flush()
                continue

            # Buyer escrowed limit price on order creation. Refund price improvement only.
            price_diff = round((buy_order.price - trade_price) * trade_qty, 2)
            if price_diff > 0:
                buyer_comp.cash = round(buyer_comp.cash + price_diff, 2)
            seller_proceeds = round(total_amount - fee, 2)
            dividend_withheld = await DividendService.accrue_cash_inflow(
                session, seller_comp, seller_proceeds, now=now
            )
            seller_comp.cash = round(
                seller_comp.cash + seller_proceeds - dividend_withheld, 2
            )

            seller_inv.quantity = round(seller_inv.quantity - trade_qty, 4)
            seller_inv.reserved_quantity = round(max(0.0, seller_inv.reserved_quantity - trade_qty), 4)

            if not buyer_inv:
                buyer_inv = NatInventory(
                    company_id=buyer_comp.id,
                    item_id=item_id,
                    quantity=trade_qty,
                    reserved_quantity=0.0,
                    avg_cost_basis=trade_price
                )
                session.add(buyer_inv)
            else:
                old_qty = buyer_inv.quantity
                new_qty = old_qty + trade_qty
                if new_qty > 0:
                    buyer_inv.avg_cost_basis = round(
                        ((old_qty * buyer_inv.avg_cost_basis) + total_amount) / new_qty, 4
                    )
                buyer_inv.quantity = round(new_qty, 4)

            # Update orders
            buy_order.remaining_qty -= trade_qty
            if buy_order.remaining_qty <= 0:
                buy_order.status = "FILLED"
                buy_order.closed_at = now

            sell_order.remaining_qty -= trade_qty
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
                total_amount=total_amount,
                fee_amount=fee,
                executed_at=now
            )
            session.add(trade)

            # Update daily financials for buyer (opex) and seller (revenue)
            today = get_game_today()
            for comp_id, rev_delta, opex_delta in [
                (buyer_comp.id, 0.0, total_amount),
                (seller_comp.id, round(total_amount - fee, 2), 0.0)
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
        locked_company = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        company = locked_company or company
        order_res = await session.execute(
            select(NatMarketOrder).where(
                NatMarketOrder.id == order_id,
                NatMarketOrder.company_id == company.id,
                NatMarketOrder.status == "ACTIVE"
            ).with_for_update()
        )
        order = order_res.scalar_one_or_none()
        if not order:
            return False

        if order.order_type == "BUY":
            refund_amount = round(order.price * order.remaining_qty, 2)
            company.cash += refund_amount
        elif order.order_type == "SELL":
            inv_res = await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == company.id,
                    NatInventory.item_id == order.item_id
                ).with_for_update()
            )
            inv = inv_res.scalar_one_or_none()
            if inv:
                inv.reserved_quantity = max(0.0, inv.reserved_quantity - order.remaining_qty)

        order.status = "CANCELLED"
        order.closed_at = get_game_now()
        if commit:
            await session.commit()
        else:
            await session.flush()
        return True
