"""Daily business income rows used by valuation, dividends and analytics."""

from datetime import date

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


__all__ = ["BusinessIncomeLedgerService"]
