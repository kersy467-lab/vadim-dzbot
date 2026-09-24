from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
import math
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from backend.natbirzha.config import nat_settings, get_game_now, get_game_today
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock, NatStockHolding, NatStockOrder, NatStockPriceSnapshot
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomeDaily
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.capital_plan_service import ipo_recommendation_level
from backend.natbirzha.services.stock_orderbook_service import StockOrderbookService

class ValuationStrategy(ABC):
    @abstractmethod
    def calculate_valuation(self, nav: float, cash: float, recent_closed_profits: List[float]) -> float:
        pass

class DefaultWeightedValuationStrategy(ValuationStrategy):
    """
    Pluggable runtime valuation formula.
    Can be modified or replaced without database migrations!
    """
    def calculate_valuation(self, nav: float, cash: float, recent_closed_profits: List[float]) -> float:
        avg_profit = sum(recent_closed_profits) / max(1, len(recent_closed_profits))
        val = (
            nav * nat_settings.IPO_NAV_WEIGHT
            + max(0.0, avg_profit) * nat_settings.IPO_PROFIT_PE_MULT
            + cash * nat_settings.IPO_CASH_DISCOUNT
        )
        return max(50000.0, round(val, 2))

current_valuation_strategy: ValuationStrategy = DefaultWeightedValuationStrategy()


class StockService:
    @staticmethod
    def blended_market_price(fair_price: float, previous_price: float, pressure: float) -> float:
        fair = max(0.01, float(fair_price))
        previous = max(0.01, float(previous_price or fair))
        imbalance = max(-1.0, min(1.0, float(pressure)))
        target = fair * (1.0 + imbalance * 0.10)
        blended = previous * 0.35 + target * 0.65
        return round(max(fair * 0.75, min(fair * 1.25, blended)), 2)

    @staticmethod
    async def record_price_snapshot(session: AsyncSession, stock: NatStock, now: datetime | None = None) -> None:
        session.add(NatStockPriceSnapshot(
            stock_id=stock.id,
            price=round(float(stock.current_price), 6),
            valuation=round(float(stock.last_valuation), 2),
            captured_at=now or get_game_now(),
        ))

    @staticmethod
    async def price_history(
        session: AsyncSession, stock_id: int, limit: int = 360, days: int | None = None
    ) -> list[dict]:
        stmt = select(NatStockPriceSnapshot).where(NatStockPriceSnapshot.stock_id == stock_id)
        if days is not None:
            stmt = stmt.where(NatStockPriceSnapshot.captured_at >= get_game_now() - timedelta(days=days))
        rows = (await session.execute(
            stmt.order_by(NatStockPriceSnapshot.captured_at.asc(), NatStockPriceSnapshot.id.asc())
        )).scalars().all()
        if len(rows) > limit:
            # Preserve the first and last real point while evenly sampling the rest.
            indexes = {round(i * (len(rows) - 1) / (limit - 1)) for i in range(limit)}
            rows = [row for index, row in enumerate(rows) if index in indexes]
        return [
            {"timestamp": row.captured_at.isoformat(), "price": row.price, "valuation": row.valuation}
            for row in rows
        ]

    @staticmethod
    async def calculate_company_valuation(
        session: AsyncSession,
        company: NatCompany,
        strategy: Optional[ValuationStrategy] = None,
    ) -> float:
        """Return the current audited valuation used for IPOs and listed shares."""
        v2_profit_rows = await session.execute(
            select(NatBusinessIncomeDaily.date, func.sum(NatBusinessIncomeDaily.net_profit))
            .join(NatBusiness, NatBusiness.id == NatBusinessIncomeDaily.business_id)
            .where(NatBusiness.company_id == company.id)
            .group_by(NatBusinessIncomeDaily.date)
            .order_by(NatBusinessIncomeDaily.date.desc())
            .limit(3)
        )
        profits = [float(value) for _, value in v2_profit_rows.all()]
        fin_res = await session.execute(
            select(NatDailyFinancials)
            .where(NatDailyFinancials.company_id == company.id)
            .order_by(NatDailyFinancials.calendar_date.desc())
            .limit(3)
        )
        if not profits:
            profits = [record.closed_profit for record in fin_res.scalars().all()]
        if not profits:
            # Keeps a young company tradable before it has closed its first day.
            profits = [company.cash * 0.1]
        valuation_strategy = strategy or current_valuation_strategy
        nav = await CompanyService.calculate_audited_nav(session, company)
        return valuation_strategy.calculate_valuation(nav, company.cash, profits)

    @staticmethod
    async def refresh_due_valuations(
        session: AsyncSession,
        now: Optional[datetime] = None,
        *,
        commit: bool = False,
    ) -> int:
        """Reprice listed shares whose company valuation is at least 10 minutes old."""
        current_time = now or get_game_now()
        refresh_before = current_time - timedelta(
            minutes=nat_settings.STOCK_VALUATION_REFRESH_MINUTES
        )
        rows = await session.execute(
            select(NatStock, NatCompany)
            .join(NatCompany, NatStock.company_id == NatCompany.id)
            .where(
                NatStock.is_listed == True,
                (NatStock.valuation_updated_at.is_(None))
                | (NatStock.valuation_updated_at <= refresh_before),
            )
        )
        refreshed = 0
        for stock, company in rows.all():
            valuation = await StockService.calculate_company_valuation(session, company)
            fair_price = valuation / max(1, stock.total_shares)
            pressure = await StockOrderbookService.market_pressure(session, stock)
            # Fundamentals remain the anchor; real order-book imbalance can move the quote
            # by up to roughly 10% around it, while the blend prevents 10-minute jumps.
            market_price = StockService.blended_market_price(
                fair_price, float(stock.current_price or fair_price), pressure
            )
            stock.last_valuation = valuation
            stock.current_price = market_price
            stock.valuation_updated_at = current_time
            await StockService.record_price_snapshot(session, stock, current_time)
            refreshed += 1
        if refreshed:
            if commit:
                await session.commit()
            else:
                await session.flush()
        return refreshed

    @staticmethod
    async def apply_for_ipo(
        session: AsyncSession,
        company: NatCompany,
        strategy: Optional[ValuationStrategy] = None,
        dividend_rate_pct: float = nat_settings.IPO_MIN_DIVIDEND_PCT,
        company_sale_pct: float = nat_settings.IPO_DEFAULT_FLOAT_PCT * 100,
        total_shares: int = nat_settings.IPO_DEFAULT_SHARES,
    ) -> NatStock:
        required_level = ipo_recommendation_level()
        if company.level < required_level:
            raise ValueError(f"Company level must be at least {required_level} for IPO.")
        if company.is_bankrupt:
            raise ValueError("Bankrupt companies cannot apply for IPO.")
        if not nat_settings.IPO_MIN_DIVIDEND_PCT <= dividend_rate_pct <= nat_settings.IPO_MAX_DIVIDEND_PCT:
            raise ValueError(
                f"Dividend rate must be between {nat_settings.IPO_MIN_DIVIDEND_PCT:g}% "
                f"and {nat_settings.IPO_MAX_DIVIDEND_PCT:g}%."
            )
        if isinstance(total_shares, bool) or not isinstance(total_shares, int) or total_shares < nat_settings.IPO_MIN_SHARES:
            raise ValueError(f"IPO share count must be at least {nat_settings.IPO_MIN_SHARES:,}.")
        maximum_sale_pct = nat_settings.IPO_FLOAT_MAX_PCT * 100
        if (
            not math.isfinite(float(company_sale_pct))
            or company_sale_pct < nat_settings.IPO_MIN_FLOAT_PCT
            or company_sale_pct > maximum_sale_pct
        ):
            raise ValueError(
                f"The company sale size must be between {nat_settings.IPO_MIN_FLOAT_PCT:g}% "
                f"and {maximum_sale_pct:g}%."
            )

        # Check if already actively listed
        existing_stock = await session.execute(
            select(NatStock).where(NatStock.company_id == company.id, NatStock.is_listed == True)
        )
        if existing_stock.scalar_one_or_none():
            raise ValueError("Company is already public.")

        valuation = await StockService.calculate_company_valuation(session, company, strategy)

        float_shares = max(1, math.floor(total_shares * float(company_sale_pct) / 100))
        founder_shares = total_shares - float_shares
        share_price = round(valuation / total_shares, 2)
        if share_price <= 0:
            raise ValueError("The selected share count makes the IPO share price too small.")

        now = get_game_now()
        stock = NatStock(
            company_id=company.id,
            total_shares=total_shares,
            founder_shares=founder_shares,
            float_shares=float_shares,
            current_price=share_price,
            last_valuation=valuation,
            dividend_rate_pct=round(float(dividend_rate_pct), 2),
            valuation_updated_at=now,
            is_listed=True,
            ipo_date=now,
            created_at=now
        )
        session.add(stock)
        await session.flush()
        await StockService.record_price_snapshot(session, stock, now)

        # Allocate founder holding (60%)
        founder_holding = NatStockHolding(
            stock_id=stock.id,
            holder_company_id=company.id,
            shares_count=founder_shares,
            avg_price=share_price,
            updated_at=now
        )
        session.add(founder_holding)

        # Place float shares (40%) on market
        float_order = NatStockOrder(
            stock_id=stock.id,
            trader_company_id=company.id,
            order_type="SELL",
            shares_count=float_shares,
            remaining_shares=float_shares,
            price=share_price,
            status="ACTIVE",
            created_at=now
        )
        session.add(float_order)

        await session.commit()
        await session.refresh(stock)
        return stock

    @staticmethod
    async def set_dividend_rate(
        session: AsyncSession,
        company: NatCompany,
        stock_id: int,
        dividend_rate_pct: float,
        *,
        commit: bool = True,
    ) -> NatStock:
        minimum = nat_settings.DIVIDEND_RATE_MIN_AFTER_IPO_PCT
        maximum = nat_settings.IPO_MAX_DIVIDEND_PCT
        if not math.isfinite(float(dividend_rate_pct)) or not minimum <= dividend_rate_pct <= maximum:
            raise ValueError(f"Dividend rate must be between {minimum:g}% and {maximum:g}%.")

        result = await session.execute(
            select(NatStock)
            .where(
                NatStock.id == stock_id,
                NatStock.company_id == company.id,
                NatStock.is_listed == True,
            )
            .with_for_update()
        )
        stock = result.scalar_one_or_none()
        if stock is None:
            raise ValueError("Listed stock was not found for this company owner.")

        stock.dividend_rate_pct = round(float(dividend_rate_pct), 2)
        if commit:
            await session.commit()
            await session.refresh(stock)
        else:
            await session.flush()
        return stock

    @staticmethod
    async def buy_shares(
        session: AsyncSession, buyer_company: NatCompany, stock_id: int, shares_to_buy: int
    ) -> Dict[str, Any]:
        """Compatibility market-buy: crosses the current best ask using the real order book."""
        if shares_to_buy <= 0:
            raise ValueError("Shares count must be positive.")
        await StockService.refresh_due_valuations(session)
        book = await StockOrderbookService.orderbook(session, stock_id, buyer_company.id)
        if book["best_ask"] is None:
            raise ValueError("No active sell orders for this stock.")
        result = await StockOrderbookService.place_limit_order(
            session, buyer_company.id, stock_id, "BUY", shares_to_buy, book["best_ask"]
        )
        spent = round(sum(row["total"] for row in result["trades"]), 2)
        return {
            "success": True, "shares_bought": sum(row["quantity"] for row in result["trades"]),
            "total_spent": spent, "order_id": result["order_id"],
            "remaining_order_shares": result["remaining"],
        }

    @staticmethod
    async def sell_shares(
        session: AsyncSession, seller_company: NatCompany, stock_id: int, shares_to_sell: int
    ) -> Dict[str, Any]:
        """Compatibility sell: crosses the best bid or leaves a real ask at the last quote."""
        if shares_to_sell <= 0:
            raise ValueError("Shares count must be positive.")
        await StockService.refresh_due_valuations(session)
        book = await StockOrderbookService.orderbook(session, stock_id, seller_company.id)
        price = book["best_bid"] or book["current_price"]
        result = await StockOrderbookService.place_limit_order(
            session, seller_company.id, stock_id, "SELL", shares_to_sell, price
        )
        received = round(sum(row["total"] for row in result["trades"]), 2)
        return {
            "success": True, "shares_sold": sum(row["quantity"] for row in result["trades"]),
            "total_payout": received, "order_id": result["order_id"],
            "remaining_order_shares": result["remaining"],
        }
