"""Company-wide 12-hour ledger of realized net profit."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.tax import NatCompanyProfitPeriod
from backend.natbirzha.tax_rules import get_period_bounds


class CompanyProfitLedgerService:
    """Record realized revenue and the expenses attributable to it."""

    @staticmethod
    async def record_period(
        session: AsyncSession,
        company_id: int,
        period_start: datetime,
        period_end: datetime,
        *,
        revenue: float = 0.0,
        financial_income: float = 0.0,
        cost_of_goods_sold: float = 0.0,
        maintenance: float = 0.0,
        salary: float = 0.0,
        other_expenses: float = 0.0,
    ) -> NatCompanyProfitPeriod | None:
        amounts = (revenue, financial_income, cost_of_goods_sold, maintenance, salary, other_expenses)
        if not any(abs(float(value or 0.0)) > 1e-9 for value in amounts):
            return None

        row = await session.scalar(
            select(NatCompanyProfitPeriod)
            .where(
                NatCompanyProfitPeriod.company_id == company_id,
                NatCompanyProfitPeriod.period_start == period_start,
            )
            .with_for_update()
        )
        if row is None:
            row = NatCompanyProfitPeriod(
                company_id=company_id,
                period_start=period_start,
                period_end=period_end,
            )
            session.add(row)
        for field, value in (
            ("realized_revenue", revenue),
            ("financial_income", financial_income),
            ("cost_of_goods_sold", cost_of_goods_sold),
            ("maintenance_expense", maintenance),
            ("salary_expense", salary),
            ("other_expenses", other_expenses),
        ):
            setattr(row, field, round(float(getattr(row, field) or 0.0) + float(value or 0.0), 6))
        await session.flush()
        return row

    @classmethod
    async def record(
        cls,
        session: AsyncSession,
        company_id: int,
        at: datetime,
        *,
        revenue: float = 0.0,
        financial_income: float = 0.0,
        cost_of_goods_sold: float = 0.0,
        maintenance: float = 0.0,
        salary: float = 0.0,
        other_expenses: float = 0.0,
    ) -> NatCompanyProfitPeriod | None:
        period_start, period_end = get_period_bounds(at.replace(tzinfo=None))
        return await cls.record_period(
            session, company_id, period_start, period_end,
            revenue=revenue,
            financial_income=financial_income,
            cost_of_goods_sold=cost_of_goods_sold,
            maintenance=maintenance,
            salary=salary,
            other_expenses=other_expenses,
        )

    @classmethod
    async def record_interval(
        cls,
        session: AsyncSession,
        company_id: int,
        start: datetime,
        worked_hours: float,
        *,
        revenue: float = 0.0,
        financial_income: float = 0.0,
        cost_of_goods_sold: float = 0.0,
        maintenance: float = 0.0,
        salary: float = 0.0,
        other_expenses: float = 0.0,
    ) -> None:
        total_seconds = max(0.0, float(worked_hours)) * 3600.0
        if total_seconds <= 1e-9:
            return
        end = start + timedelta(seconds=total_seconds)
        totals = {
            "revenue": float(revenue),
            "financial_income": float(financial_income),
            "cost_of_goods_sold": float(cost_of_goods_sold),
            "maintenance": float(maintenance),
            "salary": float(salary),
            "other_expenses": float(other_expenses),
        }
        cursor = start
        allocated_fraction = 0.0
        while cursor < end:
            period_start, period_end = get_period_bounds(cursor)
            segment_end = min(end, period_end)
            fraction = (segment_end - cursor).total_seconds() / total_seconds
            allocated_fraction += fraction
            if segment_end >= end:
                fraction += max(0.0, 1.0 - allocated_fraction)
            await cls.record_period(
                session,
                company_id,
                period_start,
                period_end,
                revenue=totals["revenue"] * fraction,
                financial_income=totals["financial_income"] * fraction,
                cost_of_goods_sold=totals["cost_of_goods_sold"] * fraction,
                maintenance=totals["maintenance"] * fraction,
                salary=totals["salary"] * fraction,
                other_expenses=totals["other_expenses"] * fraction,
            )
            cursor = segment_end


__all__ = ["CompanyProfitLedgerService"]
