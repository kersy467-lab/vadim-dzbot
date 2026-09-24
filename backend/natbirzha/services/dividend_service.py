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
        """Reconcile hourly issuer profits into a hidden dividend holdback."""
        if not hourly_profit:
            return 0.0
        stock = await session.scalar(
            select(NatStock)
            .where(NatStock.company_id == issuer.id, NatStock.is_listed == True)
            .with_for_update()
        )
        if stock is None:
            return 0.0

        current = normalize_dt(now or get_game_now())
        eligible_after = (
            normalize_dt(stock.dividend_eligible_from)
            or normalize_dt(stock.ipo_date)
            or normalize_dt(stock.created_at)
            or current
        )
        total_delta = 0.0
        for hour_start, profit_delta in sorted(hourly_profit.items()):
            hour = normalize_dt(hour_start)
            if hour is None or float(profit_delta) == 0 or hour >= current:
                continue
            row = await session.scalar(
                select(NatHourlyDividendAccrual)
                .where(
                    NatHourlyDividendAccrual.stock_id == stock.id,
                    NatHourlyDividendAccrual.hour_start == hour,
                )
                .with_for_update()
            )
            if row is not None and row.status != "OPEN":
                continue
            if row is None:
                row = NatHourlyDividendAccrual(
                    stock_id=stock.id,
                    hour_start=hour,
                    dividend_rate_pct=max(0.0, min(100.0, float(stock.dividend_rate_pct or 0))),
                )
                session.add(row)
                await session.flush()
            # Hourly splits already exclude production before IPO/rollout. This
            # guard also protects callers that pass a whole hour directly.
            if hour + timedelta(hours=1) <= eligible_after:
                continue
            old_pool = float(row.dividend_pool or 0.0)
            row.closed_profit = round(float(row.closed_profit or 0.0) + float(profit_delta), 8)
            row.dividend_pool = round(
                max(0.0, row.closed_profit) * float(row.dividend_rate_pct) / 100.0, 2
            )
            total_delta += float(row.dividend_pool) - old_pool
        await session.flush()
        return round(total_delta, 8)

    @classmethod
    async def settle_due_hourly(
        cls,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        commit: bool = False,
    ) -> Dict[str, Any]:
        """Pay closed-hour dividends once, refunding unowned shares to issuers."""
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
                holder.cash = round(float(holder.cash) + payout, 2)
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
                    holder_comp.cash = round(holder_comp.cash + payout, 2)
                    session.add(NatDividendPayment(
                        dividend_id=div_record.id,
                        stock_id=stock.id,
                        holder_company_id=h.holder_company_id,
                        shares_count=h.shares_count,
                        payout_cash=payout,
                        settlement_date=settlement_date,
                        paid_at=get_game_now(),
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
