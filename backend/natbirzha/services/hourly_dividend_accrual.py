"""Record eligible cash income in the issuer's hidden hourly dividend pool."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatHourlyDividendAccrual, NatStock


class HourlyDividendAccrualService:
    @classmethod
    async def accrue_hourly_amounts(
        cls,
        session: AsyncSession,
        issuer: NatCompany,
        hourly_amounts: dict[datetime, float],
        *,
        now: datetime | None = None,
        allow_negative_adjustments: bool = False,
    ) -> float:
        """Add cash receipts to hourly pools and return the incremental holdback."""
        if not hourly_amounts:
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
        for hour_start, amount_delta in sorted(hourly_amounts.items()):
            hour = normalize_dt(hour_start)
            amount = float(amount_delta or 0.0)
            if hour is None or hour > current or amount == 0:
                continue
            if amount < 0 and not allow_negative_adjustments:
                continue
            if hour + timedelta(hours=1) <= eligible_after:
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

            # `closed_profit` is a legacy column; it now stores eligible cash
            # receipts so the persisted ledger remains compatible without DDL.
            old_pool = float(row.dividend_pool or 0.0)
            row.closed_profit = round(float(row.closed_profit or 0.0) + amount, 8)
            row.dividend_pool = round(
                max(0.0, row.closed_profit) * float(row.dividend_rate_pct) / 100.0,
                2,
            )
            total_delta += float(row.dividend_pool) - old_pool

        await session.flush()
        return round(total_delta, 8)

    @classmethod
    async def accrue_cash_inflow(
        cls,
        session: AsyncSession,
        issuer: NatCompany,
        amount: float,
        *,
        now: datetime | None = None,
    ) -> float:
        """Hold back the configured share of one real cash income receipt."""
        current = normalize_dt(now or get_game_now())
        value = float(amount or 0.0)
        if value <= 0:
            return 0.0
        stock = await session.scalar(
            select(NatStock)
            .where(NatStock.company_id == issuer.id, NatStock.is_listed == True)
            .with_for_update()
        )
        if stock is None:
            return 0.0
        eligible_after = (
            normalize_dt(stock.dividend_eligible_from)
            or normalize_dt(stock.ipo_date)
            or normalize_dt(stock.created_at)
            or current
        )
        if current < eligible_after:
            return 0.0
        hour = current.replace(minute=0, second=0, microsecond=0)
        return await cls.accrue_hourly_amounts(
            session,
            issuer,
            {hour: value},
            now=current,
        )


__all__ = ["HourlyDividendAccrualService"]
