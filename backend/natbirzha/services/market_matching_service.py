"""Atomic execution and cash routing for commodity market orders."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.natbirzha.config import get_game_now, get_game_today, normalize_dt
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.inventory_capacity_service import InventoryCapacityService
from backend.natbirzha.services.market_advance_service import MarketAdvanceService
from backend.natbirzha.services.market_settlement import cancel_market_order, money, remaining_buy_escrow
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


MARKET_QUANTITY_DECIMALS = 6


class MarketMatchingService:
    @classmethod
    async def match_orders_for_item(cls, session: AsyncSession, item_id: str) -> int:
        trades_count = 0
        now = get_game_now()
        treasury = await MarketAdvanceService.treasury_for_order(
            session, item_id, eligible_to_advance=False
        )

        while True:
            buy_res = await session.execute(
                select(NatMarketOrder)
                .where(
                    NatMarketOrder.item_id == item_id,
                    NatMarketOrder.order_type == "BUY",
                    NatMarketOrder.status == "ACTIVE",
                    NatMarketOrder.remaining_qty > 0,
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
                buyer_user_id = await session.scalar(
                    select(NatCompany.user_id).where(NatCompany.id == candidate_buy.company_id)
                )
                seller_owner = aliased(NatCompany)
                sell_res = await session.execute(
                    select(NatMarketOrder)
                    .join(seller_owner, seller_owner.id == NatMarketOrder.company_id)
                    .where(
                        NatMarketOrder.item_id == item_id,
                        NatMarketOrder.order_type == "SELL",
                        NatMarketOrder.status == "ACTIVE",
                        NatMarketOrder.remaining_qty > 0,
                        NatMarketOrder.company_id != candidate_buy.company_id,
                        seller_owner.user_id != buyer_user_id,
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

            maker_is_sell = normalize_dt(sell_order.created_at) <= normalize_dt(buy_order.created_at)
            trade_price = sell_order.price if maker_is_sell else buy_order.price
            invalid_order = next((order for order in (buy_order, sell_order)
                                  if abs(order.remaining_qty - round(order.remaining_qty, MARKET_QUANTITY_DECIMALS)) > 1e-9), None)
            if invalid_order:
                invalid_company = (await session.execute(
                    select(NatCompany).where(NatCompany.id == invalid_order.company_id).with_for_update()
                )).scalar_one_or_none()
                if invalid_company:
                    await cancel_market_order(session, invalid_company, invalid_order.id, commit=False)
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

            buyer_comp = (await session.execute(
                select(NatCompany).where(NatCompany.id == buy_order.company_id).with_for_update()
            )).scalar_one_or_none()
            seller_comp = (await session.execute(
                select(NatCompany).where(NatCompany.id == sell_order.company_id).with_for_update()
            )).scalar_one_or_none()
            if not buyer_comp or not seller_comp or buyer_comp.user_id == seller_comp.user_id:
                break

            seller_inv = (await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == seller_comp.id,
                    NatInventory.item_id == item_id,
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
                    NatInventory.item_id == item_id,
                ).with_for_update()
            )).scalar_one_or_none()
            buyer_qty = buyer_inv.quantity if buyer_inv else 0.0
            cap = await InventoryCapacityService.for_item(session, buyer_comp, item_id)
            if buyer_qty + trade_qty > cap:
                refund = await remaining_buy_escrow(session, buy_order)
                buyer_comp.cash = float(money(Decimal(str(buyer_comp.cash)) + refund))
                buy_order.status = "CANCELLED"
                buy_order.closed_at = now
                await session.flush()
                continue

            funded_qty = min(
                max(0.0, float(sell_order.state_advance_remaining_quantity or 0.0)),
                trade_qty,
            )
            repayment = min(
                total_amount,
                money(Decimal(str(trade_price)) * Decimal(str(funded_qty)))
            ) if funded_qty > 0 else Decimal(0)
            if repayment > 0 and treasury is None:
                treasury = await StateTreasuryService.get_or_create(
                    session, commit=False, for_update=True
                )
            if repayment > 0:
                treasury.cash = float(money(Decimal(str(treasury.cash)) + repayment))
                treasury.updated_at = now

            regular_quantity = max(0.0, trade_qty - funded_qty)
            regular_gross = max(Decimal(0), total_amount - repayment)
            fee = min(money(regular_gross * Decimal("0.01")), regular_gross)
            seller_proceeds = regular_gross - fee
            MarketAdvanceService.repayment_for_fill(sell_order, trade_price, funded_qty)
            dividend_withheld = await DividendService.accrue_cash_inflow(
                session, seller_comp, float(seller_proceeds), now=now
            ) if seller_proceeds > 0 else 0.0
            seller_comp.cash = float(money(
                Decimal(str(seller_comp.cash)) + seller_proceeds - Decimal(str(dividend_withheld))
            ))
            seller_cogs = round(regular_quantity * max(0.0, float(seller_inv.avg_cost_basis or 0.0)), 6)
            if regular_gross > 0 or seller_cogs > 0 or fee > 0:
                await CompanyProfitLedgerService.record(
                    session,
                    seller_comp.id,
                    now,
                    revenue=float(regular_gross),
                    cost_of_goods_sold=seller_cogs,
                    other_expenses=float(fee),
                )

            seller_inv.quantity = round(max(0.0, seller_inv.quantity - trade_qty), MARKET_QUANTITY_DECIMALS)
            seller_inv.reserved_quantity = round(max(0.0, seller_inv.reserved_quantity - trade_qty), MARKET_QUANTITY_DECIMALS)
            if not buyer_inv:
                buyer_inv = NatInventory(
                    company_id=buyer_comp.id,
                    item_id=item_id,
                    quantity=trade_qty,
                    reserved_quantity=0.0,
                    avg_cost_basis=trade_price,
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

            session.add(NatMarketTrade(
                buy_order_id=buy_order.id,
                sell_order_id=sell_order.id,
                buyer_company_id=buyer_comp.id,
                seller_company_id=seller_comp.id,
                item_id=item_id,
                price=trade_price,
                quantity=trade_qty,
                total_amount=float(total_amount),
                fee_amount=float(fee),
                state_repayment_amount=float(repayment),
                executed_at=now,
            ))

            today = get_game_today()
            for comp_id, rev_delta, opex_delta in (
                (buyer_comp.id, 0.0, float(total_amount)),
                (seller_comp.id, float(seller_proceeds), 0.0),
            ):
                fin = await session.scalar(select(NatDailyFinancials).where(
                    NatDailyFinancials.company_id == comp_id,
                    NatDailyFinancials.calendar_date == today,
                ).with_for_update())
                if fin is None:
                    session.add(NatDailyFinancials(
                        company_id=comp_id,
                        calendar_date=today,
                        gross_revenue=rev_delta,
                        opex=opex_delta,
                        closed_profit=round(rev_delta - opex_delta, 2),
                        developer_fee_paid=0.0,
                    ))
                else:
                    fin.gross_revenue += rev_delta
                    fin.opex += opex_delta
                    fin.closed_profit = round(fin.gross_revenue - fin.opex, 2)

            trades_count += 1
            await session.flush()
        return trades_count


__all__ = ["MarketMatchingService"]
