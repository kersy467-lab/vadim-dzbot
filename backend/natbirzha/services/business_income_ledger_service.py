"""Daily business income rows used by valuation, dividends, tax and analytics."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.business import NatBusinessIncomeDaily


class BusinessIncomeLedgerService:
    @staticmethod
    def split_interval_by_hour(
        start: datetime,
        worked_hours: float,
        net_profit: float,
        *,
        eligible_after: datetime | None = None,
    ) -> dict[datetime, float]:
        """Split an operating result proportionally across eligible game hours."""
        total_seconds = max(0.0, float(worked_hours)) * 3600.0
        if total_seconds <= 1e-9:
            return {}
        end = start + timedelta(seconds=total_seconds)
        cursor = max(start, eligible_after) if eligible_after is not None else start
        if cursor >= end:
            return {}

        result: dict[datetime, float] = {}
        while cursor < end:
            hour_start = cursor.replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            segment_end = min(end, hour_end)
            seconds = (segment_end - cursor).total_seconds()
            result[hour_start] = result.get(hour_start, 0.0) + float(net_profit) * seconds / total_seconds
            cursor = segment_end
        return result

    @staticmethod
    async def record(
        session: AsyncSession,
        business_id: int,
        day: date,
        *,
        gross: float,
        maintenance: float,
        salary: float = 0.0,
        resource_cost: float = 0.0,
    ) -> None:
        """Upsert one server-settled operating result into its game-day ledger."""
        if not any((gross, maintenance, salary, resource_cost)):
            return
        row = await session.scalar(
            select(NatBusinessIncomeDaily)
            .where(NatBusinessIncomeDaily.business_id == business_id, NatBusinessIncomeDaily.date == day)
            .with_for_update()
        )
        if row is None:
            row = NatBusinessIncomeDaily(business_id=business_id, date=day)
            session.add(row)
        row.gross_income = round(float(row.gross_income or 0.0) + gross, 2)
        row.maintenance = round(float(row.maintenance or 0.0) + maintenance, 2)
        row.salary = round(float(row.salary or 0.0) + salary, 2)
        row.resource_cost = round(float(row.resource_cost or 0.0) + resource_cost, 2)
        row.net_profit = round(
            float(row.gross_income or 0.0) - float(row.maintenance or 0.0)
            - float(row.salary or 0.0) - float(row.resource_cost or 0.0), 2
        )
        await session.flush()

    @staticmethod
    async def record_period(
        session: AsyncSession,
        business_id: int,
        p_start: datetime,
        p_end: datetime,
        *,
        gross: float,
        maintenance: float,
        salary: float = 0.0,
        resource_cost: float = 0.0,
    ) -> None:
        """Upsert one 12-hour operating period result."""
        if not any((gross, maintenance, salary, resource_cost)):
            return
        from backend.natbirzha.models.business import NatBusinessIncomePeriod
        row = await session.scalar(
            select(NatBusinessIncomePeriod)
            .where(
                NatBusinessIncomePeriod.business_id == business_id,
                NatBusinessIncomePeriod.period_start == p_start,
            )
            .with_for_update()
        )
        if row is None:
            row = NatBusinessIncomePeriod(business_id=business_id, period_start=p_start, period_end=p_end)
            session.add(row)
        row.gross_income = round(float(row.gross_income or 0.0) + gross, 2)
        row.maintenance = round(float(row.maintenance or 0.0) + maintenance, 2)
        row.salary = round(float(row.salary or 0.0) + salary, 2)
        row.resource_cost = round(float(row.resource_cost or 0.0) + resource_cost, 2)
        row.net_profit = round(
            float(row.gross_income or 0.0) - float(row.maintenance or 0.0)
            - float(row.salary or 0.0) - float(row.resource_cost or 0.0), 2
        )
        await session.flush()

    @classmethod
    async def record_interval(
        cls,
        session: AsyncSession,
        business_id: int,
        start: datetime,
        worked_hours: float,
        *,
        gross: float,
        maintenance: float,
        salary: float = 0.0,
        resource_cost: float = 0.0,
    ) -> None:
        """Split one lazy-settlement result across the actual calendar days and 12-hour periods worked."""
        total_seconds = max(0.0, float(worked_hours)) * 3600.0
        if total_seconds <= 1e-9:
            return
        end = start + timedelta(seconds=total_seconds)

        # 1. Record daily ledger (for analytics and dividends)
        cursor = start
        allocated = 0.0
        while cursor < end:
            next_day = datetime.combine(cursor.date() + timedelta(days=1), time.min)
            segment_end = min(end, next_day)
            seconds = max(0.0, (segment_end - cursor).total_seconds())
            fraction = seconds / total_seconds
            allocated += fraction
            if segment_end >= end:
                fraction += max(0.0, 1.0 - allocated)
            await cls.record(
                session,
                business_id,
                cursor.date(),
                gross=gross * fraction,
                maintenance=maintenance * fraction,
                salary=salary * fraction,
                resource_cost=resource_cost * fraction,
            )
            cursor = segment_end

        # 2. Record 12-hour period ledger (for mandatory taxation)
        from backend.natbirzha.tax_rules import get_period_bounds
        p_cursor = start
        p_allocated = 0.0
        while p_cursor < end:
            p_start, p_end = get_period_bounds(p_cursor)
            segment_end = min(end, p_end)
            seconds = max(0.0, (segment_end - p_cursor).total_seconds())
            fraction = seconds / total_seconds
            p_allocated += fraction
            if segment_end >= end:
                fraction += max(0.0, 1.0 - p_allocated)
            await cls.record_period(
                session,
                business_id,
                p_start,
                p_end,
                gross=gross * fraction,
                maintenance=maintenance * fraction,
                salary=salary * fraction,
                resource_cost=resource_cost * fraction,
            )
            p_cursor = segment_end


__all__ = ["BusinessIncomeLedgerService"]
