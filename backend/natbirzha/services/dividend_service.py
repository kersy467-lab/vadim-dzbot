from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.natbirzha.config import nat_settings, get_game_today, get_game_now, normalize_dt
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import (
    NatStock,
    NatStockHolding,
    NatDividend,
    NatDividendPayment,
    NatHourlyDividendAccrual,
    NatHourlyDividendPayment,
)
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomeDaily
from backend.natbirzha.services.hourly_dividend_accrual import HourlyDividendAccrualService

class DividendService:
    @classmethod
    async def accrue_hourly_profit(
        cls,
        session: AsyncSession,
        issuer: NatCompany,
        hourly_profit: dict[datetime, float],
        *,
        now: datetime | None = None,
    ) -> float:
        """Compatibility adapter for legacy ledger corrections and callers."""
        return await HourlyDividendAccrualService.accrue_hourly_amounts(
            session, issuer, hourly_profit, now=now, allow_negative_adjustments=True
        )

    @classmethod
    async def accrue_hourly_income(
        cls,
        session: AsyncSession,
        issuer: NatCompany,
        hourly_income: dict[datetime, float],
        *,
        now: datetime | None = None,
    ) -> float:
        """Accrue hourly operating receipts before costs or daily profit are applied."""
        return await HourlyDividendAccrualService.accrue_hourly_amounts(
            session, issuer, hourly_income, now=now
        )

    @classmethod
    async def accrue_cash_inflow(
        cls,
        session: AsyncSession,
        issuer: NatCompany,
        amount: float,
        *,
        now: datetime | None = None,
    ) -> float:
        """Accrue one received dividend, coupon, or sale-proceeds amount."""
        return await HourlyDividendAccrualService.accrue_cash_inflow(
            session, issuer, amount, now=now
        )

    @classmethod
    async def settle_due_hourly(
        cls,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        commit: bool = False,
    ) -> Dict[str, Any]:
        """Pay closed-hour dividends once, refunding unowned shares to issuers."""
        from backend.natbirzha.services.sabotage_service import SabotageService
        if SabotageService.are_dividends_blocked():
            return {
                "accruals_settled": 0,
                "payment_count": 0,
                "total_paid": 0.0,
                "total_refunded": 0.0,
                "blocked": True,
            }

        current = normalize_dt(now or get_game_now())
        open_rows = (await session.execute(
            select(NatHourlyDividendAccrual)
            .where(NatHourlyDividendAccrual.status == "OPEN")
            .order_by(NatHourlyDividendAccrual.hour_start, NatHourlyDividendAccrual.id)
            .with_for_update()
        )).scalars().all()
        due_rows = [row for row in open_rows if row.hour_start + timedelta(hours=1) <= current]
        result: Dict[str, Any] = {
            "accruals_settled": 0,
            "payment_count": 0,
            "total_paid": 0.0,
            "total_refunded": 0.0,
        }
        for row in due_rows:
            stock = await session.get(NatStock, row.stock_id)
            issuer = await session.get(NatCompany, stock.company_id) if stock else None
            if stock is None:
                row.status = "SETTLED"
                row.paid_at = current
                result["accruals_settled"] += 1
                continue
            holdings = (await session.execute(
                select(NatStockHolding)
                .where(
                    NatStockHolding.stock_id == stock.id,
                    NatStockHolding.shares_count > 0,
                    NatStockHolding.holder_company_id != stock.company_id,
                )
                .order_by(NatStockHolding.holder_company_id)
                .with_for_update()
            )).scalars().all()
            investor_shares = sum(max(0, int(holding.shares_count)) for holding in holdings)
            eligible_shares = min(investor_shares, max(0, int(stock.total_shares)))
            distributable = (
                float(row.dividend_pool) * eligible_shares / max(1, int(stock.total_shares))
            )
            per_share = distributable / investor_shares if investor_shares else 0.0
            paid = 0.0
            for holding in holdings:
                remaining = max(0.0, distributable - paid)
                payout = round(min(per_share * int(holding.shares_count), remaining), 2)
                if payout <= 0:
                    continue
                holder = await session.get(NatCompany, holding.holder_company_id)
                if holder is None:
                    continue
                reinvested_dividend = await cls.accrue_cash_inflow(
                    session, holder, payout, now=current
                )
                holder.cash = round(float(holder.cash) + payout - reinvested_dividend, 2)
                session.add(NatHourlyDividendPayment(
                    accrual_id=row.id,
                    stock_id=stock.id,
                    holder_company_id=holder.id,
                    shares_count=holding.shares_count,
                    payout_cash=payout,
                    hour_start=row.hour_start,
                    paid_at=current,
                ))
                paid += payout
                result["payment_count"] += 1
            refund = round(max(0.0, float(row.dividend_pool) - paid), 2)
            if issuer is not None and refund:
                issuer.cash = round(float(issuer.cash) + refund, 2)
            row.status = "SETTLED"
            row.paid_at = current
            result["accruals_settled"] += 1
            result["total_paid"] += paid
            result["total_refunded"] += refund
        result["total_paid"] = round(result["total_paid"], 2)
        result["total_refunded"] = round(result["total_refunded"], 2)
        await session.flush()
        if commit:
            await session.commit()
        return result

    @classmethod
    async def settle_daily_dividends_for_stock(
        cls,
        session: AsyncSession,
        stock: NatStock,
        settlement_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Settles daily dividends:
          - Looks up closed cash profit for the date
          - Excludes unrealized inventory/stock gains
          - Applies the issuer's committed 5-100% profit share
          - Deducts pool from issuer company cash (checks solvency)
          - Distributes pro-rata to all shareholders in NatStockHolding
          - Idempotent per (stock_id, settlement_date)
        """
        from backend.natbirzha.services.sabotage_service import SabotageService
        if SabotageService.are_dividends_blocked():
            return {"status": "blocked", "reason": "state_default_active", "stock_id": stock.id}

        settlement_date = settlement_date or get_game_today()

        # Idempotency check: already settled for this date?
        existing_div = await session.execute(
            select(NatDividend).where(
                NatDividend.stock_id == stock.id,
                NatDividend.settlement_date == settlement_date
            )
        )
        if existing_div.scalar_one_or_none():
            return {"status": "already_settled", "stock_id": stock.id, "date": str(settlement_date)}

        # Find closed daily profit of the issuer company
        fin_res = await session.execute(
            select(NatDailyFinancials).where(
                NatDailyFinancials.company_id == stock.company_id,
                NatDailyFinancials.calendar_date == settlement_date
            )
        )
        fin = fin_res.scalar_one_or_none()
        v2_profit = await session.scalar(
            select(func.sum(NatBusinessIncomeDaily.net_profit))
            .join(NatBusiness, NatBusiness.id == NatBusinessIncomeDaily.business_id)
            .where(
                NatBusiness.company_id == stock.company_id,
                NatBusinessIncomeDaily.date == settlement_date,
            )
        )
        # V2 businesses have their own server-settled profit ledger; legacy
        # production continues to use NatDailyFinancials during rollout.
        closed_profit = float(v2_profit) if v2_profit is not None else (fin.closed_profit if fin else 0.0)

        issuer_comp = await session.get(NatCompany, stock.company_id)

        if closed_profit <= 0 or not issuer_comp or issuer_comp.cash <= 0:
            # Zero or negative profit / insolvent issuer -> 0 dividend
            div_record = NatDividend(
                stock_id=stock.id,
                settlement_date=settlement_date,
                closed_profit=closed_profit,
                dividend_pool=0.0,
                per_share_amount=0.0,
                is_settled=True,
                created_at=get_game_now()
            )
            session.add(div_record)
            await session.commit()
            return {"status": "zero_profit", "stock_id": stock.id, "closed_profit": closed_profit}

        holdings_res = await session.execute(
            select(NatStockHolding).where(NatStockHolding.stock_id == stock.id)
        )
        holdings = holdings_res.scalars().all()
        held_shares = sum(max(0, int(holding.shares_count)) for holding in holdings)
        total_shares = max(1, int(stock.total_shares))

        dividend_rate_pct = float(
            getattr(stock, "dividend_rate_pct", nat_settings.DIVIDEND_POOL_PCT * 100)
            or nat_settings.DIVIDEND_POOL_PCT * 100
        )
        declared_pool = round(closed_profit * dividend_rate_pct / 100, 2)
        # Only shares held by investors receive cash. Unsold float shares stay
        # with the issuer instead of being debited into an unclaimed pool.
        desired_pool = round(declared_pool * min(held_shares, total_shares) / total_shares, 2)
        dividend_pool = min(desired_pool, round(issuer_comp.cash, 2))

        if dividend_pool <= 0:
            div_record = NatDividend(
                stock_id=stock.id,
                settlement_date=settlement_date,
                closed_profit=closed_profit,
                dividend_pool=0.0,
                per_share_amount=0.0,
                is_settled=True,
                created_at=get_game_now()
            )
            session.add(div_record)
            await session.commit()
            return {"status": "zero_profit", "stock_id": stock.id, "closed_profit": closed_profit}

        # Deduct dividend pool from issuer company cash (no money out of thin air)
        issuer_comp.cash = round(issuer_comp.cash - dividend_pool, 2)

        per_share = round(dividend_pool / held_shares, 4) if held_shares else 0.0

        # Record the settlement before creating immutable per-holder receipts.
        div_record = NatDividend(
            stock_id=stock.id,
            settlement_date=settlement_date,
            closed_profit=closed_profit,
            dividend_pool=dividend_pool,
            per_share_amount=per_share,
            is_settled=True,
            created_at=get_game_now()
        )
        session.add(div_record)
        await session.flush()

        # Distribute dividend payouts to shareholders and retain a receipt so
        # portfolio history remains correct even if shares are sold later.
        for h in holdings:
            payout = round(h.shares_count * per_share, 2)
            if payout > 0:
                holder_comp = await session.get(NatCompany, h.holder_company_id)
                if holder_comp:
                    paid_at = get_game_now()
                    reinvested_dividend = await cls.accrue_cash_inflow(
                        session, holder_comp, payout, now=paid_at
                    )
                    holder_comp.cash = round(
                        holder_comp.cash + payout - reinvested_dividend, 2
                    )
                    session.add(NatDividendPayment(
                        dividend_id=div_record.id,
                        stock_id=stock.id,
                        holder_company_id=h.holder_company_id,
                        shares_count=h.shares_count,
                        payout_cash=payout,
                        settlement_date=settlement_date,
                        paid_at=paid_at,
                    ))
        await session.commit()

        return {
            "status": "settled",
            "stock_id": stock.id,
            "closed_profit": closed_profit,
            "dividend_pool": dividend_pool,
            "per_share": per_share,
            "shareholders_count": len(holdings)
        }

    @classmethod
    async def settle_all_public_dividends(cls, session: AsyncSession) -> int:
        """Global daily job executed at 00:01 GAME_TIMEZONE for the closed previous day."""
        stocks_res = await session.execute(select(NatStock).where(NatStock.is_listed == True))
        stocks = stocks_res.scalars().all()
        settled_count = 0
        yesterday = get_game_today() - timedelta(days=1)
        for s in stocks:
            res = await cls.settle_daily_dividends_for_stock(session, s, yesterday)
            if res.get("status") in ("settled", "zero_profit"):
                settled_count += 1
        return settled_count
