from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.natbirzha.config import nat_settings, get_game_today, get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock, NatStockHolding, NatDividend, NatDividendPayment
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomeDaily

class DividendService:
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
          - Allocates 10% pool
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

        dividend_rate_pct = float(
            getattr(stock, "dividend_rate_pct", nat_settings.DIVIDEND_POOL_PCT * 100)
            or nat_settings.DIVIDEND_POOL_PCT * 100
        )
        desired_pool = round(closed_profit * dividend_rate_pct / 100, 2)
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

        per_share = round(dividend_pool / stock.total_shares, 4)

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
        holdings_res = await session.execute(
            select(NatStockHolding).where(NatStockHolding.stock_id == stock.id)
        )
        holdings = holdings_res.scalars().all()

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
