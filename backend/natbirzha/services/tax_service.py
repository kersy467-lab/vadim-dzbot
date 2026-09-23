"""Mandatory daily profit tax, grace period, penalties and production blocking."""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, nat_settings
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomeDaily
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.tax import NatTaxDaily
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService
from backend.natbirzha.tax_rules import grace_until, production_deadline


class TaxService:
    """Authoritative 13% tax on positive closed-day V2 operating profit."""

    _grace_until = staticmethod(grace_until)

    @classmethod
    def _is_overdue(cls, row: NatTaxDaily, today: date) -> bool:
        return row.outstanding > 0 and today > cls._grace_until(row.tax_date)

    @staticmethod
    async def _profit_by_day(session: AsyncSession, company_id: int, before: date) -> dict[date, float]:
        rows = (await session.execute(
            select(NatBusinessIncomeDaily.date, func.sum(NatBusinessIncomeDaily.net_profit))
            .join(NatBusiness, NatBusiness.id == NatBusinessIncomeDaily.business_id)
            .where(NatBusiness.company_id == company_id, NatBusinessIncomeDaily.date < before)
            .group_by(NatBusinessIncomeDaily.date)
        )).all()
        return {day: round(float(profit or 0.0), 2) for day, profit in rows}

    @staticmethod
    async def _today_profit(session: AsyncSession, company_id: int, today: date) -> float:
        value = await session.scalar(
            select(func.sum(NatBusinessIncomeDaily.net_profit))
            .join(NatBusiness, NatBusiness.id == NatBusinessIncomeDaily.business_id)
            .where(NatBusiness.company_id == company_id, NatBusinessIncomeDaily.date == today)
        )
        return round(float(value or 0.0), 2)

    @classmethod
    async def sync_company(
        cls, session: AsyncSession, company_id: int, *, today: date | None = None
    ) -> list[NatTaxDaily]:
        """Create closed-day liabilities and assess non-compounding overdue penalties."""
        current_day = today or get_game_now().date()
        profits = await cls._profit_by_day(session, company_id, current_day)
        rows = list((await session.execute(
            select(NatTaxDaily)
            .where(NatTaxDaily.company_id == company_id)
            .order_by(NatTaxDaily.tax_date)
            .with_for_update()
        )).scalars().all())
        by_day = {row.tax_date: row for row in rows}
        rate = max(0.0, float(nat_settings.TAX_RATE))

        for profit_day, profit in profits.items():
            taxable = max(0.0, profit)
            principal = round(taxable * rate, 2)
            if principal <= 0 and profit_day not in by_day:
                continue
            row = by_day.get(profit_day)
            if row is None:
                row = NatTaxDaily(
                    company_id=company_id,
                    tax_date=profit_day,
                    taxable_profit=taxable,
                    principal=principal,
                    last_penalty_day=cls._grace_until(profit_day),
                )
                session.add(row)
                rows.append(row)
                by_day[profit_day] = row
            else:
                row.taxable_profit = taxable
                row.principal = principal

        penalty_rate = max(0.0, float(nat_settings.TAX_DAILY_PENALTY_RATE))
        for row in rows:
            grace_until = cls._grace_until(row.tax_date)
            if row.last_penalty_day is None or row.last_penalty_day < grace_until:
                row.last_penalty_day = grace_until
            if row.outstanding <= 0 or current_day <= grace_until:
                continue
            from_day = max(grace_until, row.last_penalty_day)
            extra_days = max(0, (current_day - from_day).days)
            if extra_days:
                row.penalty = round(float(row.penalty or 0.0) + row.principal * penalty_rate * extra_days, 2)
                row.last_penalty_day = current_day

        await session.flush()
        return sorted(rows, key=lambda row: row.tax_date)

    @classmethod
    async def summary(
        cls, session: AsyncSession, company_id: int, *, today: date | None = None
    ) -> dict:
        current_day = today or get_game_now().date()
        rows = await cls.sync_company(session, company_id, today=current_day)
        unpaid = [row for row in rows if row.outstanding > 0]
        blocked = any(cls._is_overdue(row, current_day) for row in unpaid)
        oldest = unpaid[0] if unpaid else None
        principal_due = sum(max(0.0, row.principal - min(row.paid_amount, row.principal)) for row in unpaid)
        total_due = sum(row.outstanding for row in unpaid)
        penalty_due = max(0.0, total_due - principal_due)
        next_block_date = cls._grace_until(oldest.tax_date) + timedelta(days=1) if oldest else None
        today_profit = await cls._today_profit(session, company_id, current_day)
        return {
            "rate": float(nat_settings.TAX_RATE),
            "rate_pct": round(float(nat_settings.TAX_RATE) * 100, 2),
            "grace_days": int(nat_settings.TAX_GRACE_DAYS),
            "daily_penalty_rate": float(nat_settings.TAX_DAILY_PENALTY_RATE),
            "daily_penalty_pct": round(float(nat_settings.TAX_DAILY_PENALTY_RATE) * 100, 2),
            "principal_due": round(principal_due, 2),
            "penalty_due": round(penalty_due, 2),
            "total_due": round(total_due, 2),
            "blocked": blocked,
            "oldest_unpaid_date": oldest.tax_date.isoformat() if oldest else None,
            "next_block_date": next_block_date.isoformat() if next_block_date else None,
            "days_until_block": max(0, (next_block_date - current_day).days) if next_block_date else None,
            "today_profit": today_profit,
            "today_estimated_tax": round(max(0.0, today_profit) * float(nat_settings.TAX_RATE), 2),
            "liabilities": [cls._serialize_row(row, current_day) for row in reversed(rows[-14:])],
        }

    @classmethod
    def _serialize_row(cls, row: NatTaxDaily, today: date) -> dict:
        return {
            "tax_date": row.tax_date.isoformat(),
            "taxable_profit": round(float(row.taxable_profit), 2),
            "principal": round(float(row.principal), 2),
            "penalty": round(float(row.penalty), 2),
            "paid": round(float(row.paid_amount), 2),
            "outstanding": row.outstanding,
            "grace_until": cls._grace_until(row.tax_date).isoformat(),
            "overdue": cls._is_overdue(row, today),
        }

    @classmethod
    async def pay(
        cls, session: AsyncSession, company_id: int, amount: float | None = None
    ) -> dict:
        # Tax deposits and state-share/bond payouts share this Treasury row.
        # Always lock Treasury before a company to avoid cross-instrument cycles.
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if company is None:
            raise ValueError("Компания не найдена")
        rows = await cls.sync_company(session, company_id)
        due = round(sum(row.outstanding for row in rows), 2)
        if due <= 0:
            return await cls.summary(session, company_id)
        payment = due if amount is None else min(due, round(float(amount), 2))
        if payment <= 0:
            raise ValueError("Сумма налога должна быть больше нуля")
        if float(company.cash) + 1e-9 < payment:
            raise ValueError(f"Недостаточно cash: требуется {payment:.2f}")

        remaining = payment
        for row in rows:
            if remaining <= 1e-9 or row.outstanding <= 0:
                continue
            part = min(remaining, row.outstanding)
            row.paid_amount = round(float(row.paid_amount or 0.0) + part, 2)
            remaining = round(remaining - part, 2)
        company.cash = round(float(company.cash) - payment, 2)
        treasury.cash = round(float(treasury.cash) + payment, 2)
        await EconomyMetricsService.record(
            session, company_id=company.id, flow="SINK", category="daily_profit_tax", cash_amount=payment
        )
        await session.flush()
        result = await cls.summary(session, company_id)
        result["paid_now"] = payment
        result["cash"] = round(float(company.cash), 2)
        return result

    production_deadline = staticmethod(production_deadline)


__all__ = ["TaxService"]
