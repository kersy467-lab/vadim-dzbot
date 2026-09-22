"""Daily business income rows used by valuation, dividends, tax and analytics."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.business import NatBusinessIncomeDaily


class BusinessIncomeLedgerService:
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
        """Split one lazy-settlement result across the actual calendar days worked."""
        total_seconds = max(0.0, float(worked_hours)) * 3600.0
        if total_seconds <= 1e-9:
            return
        end = start + timedelta(seconds=total_seconds)
        cursor = start
        allocated = 0.0
        while cursor < end:
            next_day = datetime.combine(cursor.date() + timedelta(days=1), time.min)
            segment_end = min(end, next_day)
            seconds = max(0.0, (segment_end - cursor).total_seconds())
            fraction = seconds / total_seconds
            allocated += fraction
            # Give the final segment the rounding remainder so totals stay exact.
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


__all__ = ["BusinessIncomeLedgerService"]
