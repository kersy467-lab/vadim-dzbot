"""State cash advances backed by reserved player-market sell inventory."""

from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.natbirzha.config import get_game_now, get_game_today, normalize_dt
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.market_settlement import money
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


ADVANCE_LIMIT = Decimal("30000.00")
ADVANCE_QUANTITY_DECIMALS = 6
REFERENCE_WINDOW = timedelta(hours=24)
REFERENCE_TRADE_LIMIT = 48
MIN_REFERENCE_TRADES = 3
ADVANCE_EPSILON = 1e-9


class MarketAdvanceService:
    @staticmethod
    async def preserve_collateral_during_bankruptcy(
        session: AsyncSession, order: NatMarketOrder,
    ) -> None:
        """Keep financed inventory reserved while freeing any unfunded tail."""
        inventory = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == order.company_id,
            NatInventory.item_id == order.item_id,
        ).with_for_update())
        protected = min(
            max(0.0, float(order.remaining_qty or 0.0)),
            max(0.0, float(order.state_advance_remaining_quantity or 0.0)),
        )
        released = max(0.0, float(order.remaining_qty or 0.0) - protected)
        if inventory is not None and released > ADVANCE_EPSILON:
            inventory.reserved_quantity = max(0.0, float(inventory.reserved_quantity or 0.0) - released)
        order.remaining_qty = protected

    @staticmethod
    async def external_trade_history(
        session: AsyncSession, item_id: str, *, limit: int = REFERENCE_TRADE_LIMIT,
        since=None,
    ) -> list[NatMarketTrade]:
        buyer_owner = aliased(NatCompany)
        seller_owner = aliased(NatCompany)
        stmt = (
            select(NatMarketTrade)
            .join(buyer_owner, buyer_owner.id == NatMarketTrade.buyer_company_id)
            .join(seller_owner, seller_owner.id == NatMarketTrade.seller_company_id)
            .where(
                NatMarketTrade.item_id == item_id,
                buyer_owner.user_id != seller_owner.user_id,
                NatMarketTrade.price > 0,
                NatMarketTrade.quantity > 0,
                NatMarketTrade.total_amount > 0,
            )
            .order_by(NatMarketTrade.executed_at.desc(), NatMarketTrade.id.desc())
            .limit(limit)
        )
        if since is not None:
            stmt = stmt.where(NatMarketTrade.executed_at >= normalize_dt(since))
        result = await session.execute(stmt)
        return result.scalars().all()

    @classmethod
    def reference_price_from_history(cls, history, *, now=None) -> float | None:
        """Use recent, independent trade evidence to calculate the advance limit."""
        current = normalize_dt(now or get_game_now())
        recent_history = [
            trade for trade in history
            if normalize_dt(trade.executed_at) >= current - REFERENCE_WINDOW
        ]
        counterparties = {
            tuple(sorted((int(trade.buyer_company_id), int(trade.seller_company_id))))
            for trade in recent_history
        }
        if len(recent_history) < MIN_REFERENCE_TRADES or len(counterparties) < 2:
            return None
        last_price = float(recent_history[0].price)
        median_price = float(median(float(trade.price) for trade in recent_history))
        return round(min(last_price, median_price), 6)

    @classmethod
    async def reference_price(cls, session: AsyncSession, item_id: str, *, now=None) -> float | None:
        """Use the visible latest trade only when 24h market evidence supports it."""
        current = normalize_dt(now or get_game_now())
        history = await cls.external_trade_history(
            session, item_id, since=current - REFERENCE_WINDOW
        )
        return cls.reference_price_from_history(history, now=current)

    @staticmethod
    async def has_active_advances(session: AsyncSession, item_id: str) -> bool:
        return bool(await session.scalar(
            select(NatMarketOrder.id).where(
                NatMarketOrder.item_id == item_id,
                NatMarketOrder.order_type == "SELL",
                NatMarketOrder.status == "ACTIVE",
                NatMarketOrder.remaining_qty > 0,
                NatMarketOrder.state_advance_remaining_quantity > ADVANCE_EPSILON,
            ).limit(1)
        ))

    @classmethod
    async def treasury_for_order(
        cls, session: AsyncSession, item_id: str, *, eligible_to_advance: bool,
    ) -> NatStateTreasury | None:
        if not eligible_to_advance and not await cls.has_active_advances(session, item_id):
            return None
        return await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )

    @classmethod
    async def fund_sell_order(
        cls,
        session: AsyncSession,
        company: NatCompany,
        inventory,
        order: NatMarketOrder,
        treasury: NatStateTreasury | None,
        reference_price: float | None,
        *,
        now=None,
    ) -> float:
        order.state_advance_reference_price = reference_price
        if reference_price is None:
            order.state_advance_reason = "NO_MARKET_REFERENCE"
            return 0.0
        if float(order.price) > reference_price + ADVANCE_EPSILON:
            order.state_advance_reason = "PRICE_ABOVE_REFERENCE"
            return 0.0
        if treasury is None:
            order.state_advance_reason = "TREASURY_UNAVAILABLE"
            return 0.0

        price = Decimal(str(order.price))
        available = min(
            ADVANCE_LIMIT,
            money(price * Decimal(str(order.remaining_qty))),
            money(max(0.0, float(treasury.cash or 0.0))),
        )
        quantity = (available / price).quantize(
            Decimal("0.000001"), rounding=ROUND_DOWN
        )
        advance = money(price * quantity)
        quantum = Decimal("0.000001")
        while quantity > 0 and advance > available:
            quantity -= quantum
            advance = money(price * quantity)
        if quantity <= 0 or advance <= 0:
            order.state_advance_reason = "TREASURY_EMPTY"
            return 0.0

        current = normalize_dt(now or get_game_now())
        funded_quantity = round(float(quantity), ADVANCE_QUANTITY_DECIMALS)
        advance_cash = float(advance)
        withheld = await DividendService.accrue_cash_inflow(
            session, company, advance_cash, now=current
        )
        company.cash = float(money(Decimal(str(company.cash or 0.0)) + advance - Decimal(str(withheld))))
        treasury.cash = float(money(Decimal(str(treasury.cash)) - advance))
        treasury.updated_at = current
        inventory_cost = funded_quantity * max(0.0, float(inventory.avg_cost_basis or 0.0))
        await CompanyProfitLedgerService.record(
            session, company.id, current,
            revenue=advance_cash,
            cost_of_goods_sold=inventory_cost,
        )
        await cls._record_daily_revenue(session, company.id, advance_cash, current)

        order.state_advance_amount = advance_cash
        order.state_advance_quantity = funded_quantity
        order.state_advance_remaining_amount = advance_cash
        order.state_advance_remaining_quantity = funded_quantity
        order.state_advance_reason = "ADVANCED"
        return advance_cash

    @staticmethod
    async def _record_daily_revenue(
        session: AsyncSession, company_id: int, revenue: float, now,
    ) -> None:
        today = get_game_today()
        row = await session.scalar(
            select(NatDailyFinancials).where(
                NatDailyFinancials.company_id == company_id,
                NatDailyFinancials.calendar_date == today,
            ).with_for_update()
        )
        if row is None:
            row = NatDailyFinancials(
                company_id=company_id,
                calendar_date=today,
                gross_revenue=revenue,
                opex=0.0,
                closed_profit=round(revenue, 2),
                developer_fee_paid=0.0,
            )
            session.add(row)
        else:
            row.gross_revenue = round(float(row.gross_revenue) + revenue, 2)
            row.closed_profit = round(float(row.gross_revenue) - float(row.opex), 2)

    @staticmethod
    def repayment_for_fill(order: NatMarketOrder, trade_price: float, trade_quantity: float) -> tuple[float, float]:
        funded_qty = min(
            max(0.0, float(order.state_advance_remaining_quantity or 0.0)),
            max(0.0, float(trade_quantity)),
        )
        if funded_qty <= ADVANCE_EPSILON:
            return 0.0, 0.0
        repayment = float(money(Decimal(str(trade_price)) * Decimal(str(funded_qty))))
        if funded_qty + ADVANCE_EPSILON >= float(order.state_advance_remaining_quantity):
            principal_reduced = float(order.state_advance_remaining_amount or 0.0)
            order.state_advance_remaining_quantity = 0.0
            order.state_advance_remaining_amount = 0.0
        else:
            old_qty = Decimal(str(order.state_advance_remaining_quantity))
            old_amount = Decimal(str(order.state_advance_remaining_amount or 0.0))
            new_qty = max(Decimal(0), old_qty - Decimal(str(funded_qty)))
            new_amount = money(old_amount * new_qty / old_qty) if old_qty else Decimal(0)
            principal_reduced = float(old_amount - new_amount)
            order.state_advance_remaining_quantity = float(new_qty)
            order.state_advance_remaining_amount = float(new_amount)
        return repayment, principal_reduced


__all__ = ["MarketAdvanceService", "ADVANCE_LIMIT"]
