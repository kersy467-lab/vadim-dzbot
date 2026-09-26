"""Mandatory 12-hour net-profit tax, immediate production blocking and 3% hourly simple penalty."""

from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.tax import NatCompanyProfitPeriod, NatTaxPeriod
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService
from backend.natbirzha.tax_rules import (
    calculate_hourly_penalty,
    get_period_bounds,
    overdue_hours,
    period_grace_until,
    period_production_deadline,
)


def _normalize_time(now: datetime | None = None, today: date | None = None) -> datetime:
    if now is not None:
        return now.replace(microsecond=0)
    if today is not None:
        if isinstance(today, datetime):
            return today.replace(microsecond=0)
        return datetime.combine(today, time(23, 59, 59))
    return get_game_now().replace(microsecond=0)


class TaxService:
    """Tax positive realized net profit per closed 12-hour period; penalties are simple +3%/hour."""

    @classmethod
    def _is_overdue(cls, row: NatTaxPeriod, now: datetime) -> bool:
        return row.outstanding > 0 and now >= period_grace_until(row.period_end)

    @classmethod
    async def _profit_by_period(
        cls, session: AsyncSession, company_id: int, before: datetime
    ) -> dict[tuple[datetime, datetime], float]:
        """Return realized net profit for all closed company periods."""
        rows = (await session.execute(
            select(NatCompanyProfitPeriod).where(
                NatCompanyProfitPeriod.company_id == company_id,
                NatCompanyProfitPeriod.period_end <= before,
            )
        )).scalars().all()
        return {
            (row.period_start, row.period_end): round(float(row.net_profit), 2)
            for row in rows
        }

    @classmethod
    async def _current_period_profit(cls, session: AsyncSession, company_id: int, now: datetime) -> float:
        p_start, _ = get_period_bounds(now)
        row = await session.scalar(select(NatCompanyProfitPeriod).where(
            NatCompanyProfitPeriod.company_id == company_id,
            NatCompanyProfitPeriod.period_start == p_start,
        ))
        return round(float(row.net_profit), 2) if row is not None else 0.0

    @classmethod
    async def sync_company(
        cls,
        session: AsyncSession,
        company_id: int,
        *,
        now: datetime | None = None,
        today: date | None = None,
    ) -> list[NatTaxPeriod]:
        """Create closed 12-hour period liabilities and assess non-compounding +3%/hour overdue penalties."""
        current_dt = _normalize_time(now=now, today=today)
        profits = await cls._profit_by_period(session, company_id, before=current_dt)
        rows = list((await session.execute(
            select(NatTaxPeriod)
            .where(NatTaxPeriod.company_id == company_id)
            .order_by(NatTaxPeriod.period_start)
            .with_for_update()
        )).scalars().all())
        by_start = {row.period_start: row for row in rows}
        rate = max(0.0, float(nat_settings.TAX_RATE))

        for (p_start, p_end), profit in profits.items():
            taxable = max(0.0, profit)
            principal = round(taxable * rate, 2)
            if principal <= 0 and p_start not in by_start:
                continue
            row = by_start.get(p_start)
            if row is None:
                row = NatTaxPeriod(
                    company_id=company_id,
                    period_start=p_start,
                    period_end=p_end,
                    taxable_profit=taxable,
                    principal=principal,
                    last_penalty_at=period_grace_until(p_end),
                )
                session.add(row)
                rows.append(row)
                by_start[p_start] = row
            # Existing liabilities are immutable at rollout. In particular,
            # historical rows must not be erased or recalculated from the new
            # realized-sales ledger after their old basis has been frozen.

        for row in rows:
            grace = period_grace_until(row.period_end)
            if row.outstanding <= 0:
                continue
            if current_dt > grace:
                hrs = overdue_hours(row.period_end, current_dt)
                row.penalty = calculate_hourly_penalty(row.principal, hrs)
                row.last_penalty_at = current_dt
            else:
                row.penalty = 0.0

        await session.flush()
        return sorted(rows, key=lambda row: row.period_start)

    @classmethod
    async def summary(
        cls,
        session: AsyncSession,
        company_id: int,
        *,
        now: datetime | None = None,
        today: date | None = None,
    ) -> dict:
        current_dt = _normalize_time(now=now, today=today)
        rows = await cls.sync_company(session, company_id, now=current_dt)
        unpaid = [row for row in rows if row.outstanding > 0]
        blocked = any(cls._is_overdue(row, current_dt) for row in unpaid)
        oldest = unpaid[0] if unpaid else None
        principal_due = sum(max(0.0, row.principal - min(row.paid_amount, row.principal)) for row in unpaid)
        total_due = sum(row.outstanding for row in unpaid)
        penalty_due = max(0.0, total_due - principal_due)
        next_block_dt = period_grace_until(oldest.period_end) if oldest else None
        current_profit = await cls._current_period_profit(session, company_id, current_dt)
        effective_rate = float(nat_settings.TAX_RATE)
        hours_until_block = max(0, int((next_block_dt - current_dt).total_seconds() // 3600)) if next_block_dt else None

        return {
            "rate": float(effective_rate),
            "rate_pct": round(float(effective_rate) * 100, 2),
            "period_hours": int(nat_settings.TAX_PERIOD_HOURS),
            "grace_hours": int(nat_settings.TAX_GRACE_HOURS),
            "grace_days": round(int(nat_settings.TAX_GRACE_HOURS) / 24, 2),
            "hourly_penalty_rate": float(nat_settings.TAX_HOURLY_PENALTY_RATE),
            "hourly_penalty_pct": round(float(nat_settings.TAX_HOURLY_PENALTY_RATE) * 100, 2),
            "daily_penalty_rate": float(nat_settings.TAX_DAILY_PENALTY_RATE),
            "daily_penalty_pct": round(float(nat_settings.TAX_DAILY_PENALTY_RATE) * 100, 2),
            "principal_due": round(principal_due, 2),
            "penalty_due": round(penalty_due, 2),
            "total_due": round(total_due, 2),
            "blocked": blocked,
            "oldest_unpaid_date": oldest.period_end.isoformat() if oldest else None,
            "next_block_date": next_block_dt.isoformat() if next_block_dt else None,
            "hours_until_block": hours_until_block,
            "days_until_block": max(0, int((next_block_dt - current_dt).total_seconds() // 86400)) if next_block_dt else None,
            "current_period_realized_profit": current_profit,
            "current_period_estimated_tax": round(max(0.0, current_profit) * float(effective_rate), 2),
            "liabilities": [cls._serialize_row(row, current_dt) for row in reversed(rows[-14:])],
        }

    @classmethod
    def _serialize_row(cls, row: NatTaxPeriod, now: datetime) -> dict:
        grace = period_grace_until(row.period_end)
        overdue = cls._is_overdue(row, now)
        return {
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "tax_date": row.period_start.strftime("%Y-%m-%d %H:%M"),
            "taxable_profit": round(float(row.taxable_profit), 2),
            "principal": round(float(row.principal), 2),
            "penalty": round(float(row.penalty), 2),
            "paid": round(float(row.paid_amount), 2),
            "outstanding": row.outstanding,
            "grace_until": grace.isoformat(),
            "overdue": overdue,
            "overdue_hours": overdue_hours(row.period_end, now) if overdue else 0,
        }

    @staticmethod
    def production_deadline(val: datetime | date) -> datetime:
        if isinstance(val, datetime):
            if val.minute == 0 and val.second == 0 and val.hour in (0, 12):
                return period_grace_until(val)
            _, p_end = get_period_bounds(val)
            return period_production_deadline(p_end)
        p_end = datetime.combine(val, time(12, 0, 0))
        return period_production_deadline(p_end)

    @classmethod
    async def pay(
        cls, session: AsyncSession, company_id: int, amount: float | None = None
    ) -> dict:
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
            summary = await cls.summary(session, company_id)
            return {**summary, "paid_now": 0.0, "cash": company.cash}
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
            session, company_id=company.id, flow="SINK", category="period_profit_tax", cash_amount=payment
        )
        await session.flush()
        summary = await cls.summary(session, company_id)
        return {**summary, "paid_now": payment, "cash": company.cash}


__all__ = ["TaxService"]
