"""Limited midgame debt: an alternative to dilution, not a free money faucet."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.contracts import NatLoan
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService


MIN_LOAN_LEVEL = 14
MIN_PRINCIPAL = 25_000.0
LOAN_TERM_DAYS = 14
MAX_DEBT_TO_NAV = 0.35
BASE_DAILY_RATE = 0.006


class LoanService:
    @staticmethod
    def _naive(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt

    @classmethod
    def _accrue(cls, loan: NatLoan, now: datetime) -> None:
        if loan.status != "ACTIVE":
            return
        current = cls._naive(now)
        anchor = cls._naive(loan.last_accrued_at or loan.created_at or current)
        elapsed_days = max(0.0, (current - anchor).total_seconds() / 86400.0)
        if elapsed_days > 0:
            loan.remaining_debt = round(
                float(loan.remaining_debt) * ((1.0 + float(loan.daily_interest_rate)) ** elapsed_days), 2
            )
            loan.last_accrued_at = current
        if current.date() > loan.due_date and loan.remaining_debt > 0:
            loan.status = "DEFAULTED"

    @staticmethod
    def quote(company: NatCompany, active_debt: float = 0.0, nav: float | None = None) -> dict[str, Any]:
        level = int(company.level or 1)
        debt = max(0.0, float(active_debt or 0.0))
        gross_nav = max(0.0, float(nav if nav is not None else company.cash or 0.0))
        # Borrowed cash is an asset and a liability. Remove current debt before sizing the next credit line.
        net_nav = max(0.0, gross_nav - debt)
        debt_limit = min(2_500_000.0, net_nav * MAX_DEBT_TO_NAV)
        available = max(0.0, debt_limit - debt)
        rate = max(0.0035, BASE_DAILY_RATE - max(0, level - MIN_LOAN_LEVEL) * 0.00003)
        return {
            "eligible": level >= MIN_LOAN_LEVEL and available >= MIN_PRINCIPAL,
            "required_level": MIN_LOAN_LEVEL,
            "max_debt_to_nav": MAX_DEBT_TO_NAV,
            "net_nav": round(net_nav, 2),
            "debt_limit": round(debt_limit, 2),
            "max_principal": round(available, 2),
            "min_principal": MIN_PRINCIPAL,
            "daily_interest_rate": round(rate, 6),
            "daily_interest_pct": round(rate * 100, 3),
            "term_days": LOAN_TERM_DAYS,
        }

    @classmethod
    async def _active_loans(cls, session: AsyncSession, company_id: int, *, for_update: bool = False) -> list[NatLoan]:
        stmt = select(NatLoan).where(
            NatLoan.company_id == company_id,
            NatLoan.status.in_(("ACTIVE", "DEFAULTED")),
        ).order_by(NatLoan.id.asc())
        if for_update:
            stmt = stmt.with_for_update()
        return list((await session.execute(stmt)).scalars().all())

    @classmethod
    async def status(cls, session: AsyncSession, company: NatCompany) -> dict[str, Any]:
        now = get_game_now()
        loans = await cls._active_loans(session, company.id, for_update=True)
        for loan in loans:
            cls._accrue(loan, now)
        debt_total = round(sum(float(x.remaining_debt) for x in loans if x.status in {"ACTIVE", "DEFAULTED"}), 2)
        from backend.natbirzha.services.company_service import CompanyService
        nav = await CompanyService.calculate_audited_nav(session, company)
        quote = cls.quote(company, debt_total, nav=nav)
        if any(x.status == "DEFAULTED" for x in loans):
            quote["eligible"] = False
            quote["blocked_reason"] = "defaulted_debt"
        await session.flush()
        return {
            "quote": quote,
            "loans": [cls.serialize(x) for x in loans],
            "active_debt": debt_total,
        }

    @classmethod
    async def borrow(cls, session: AsyncSession, company: NatCompany, principal: float) -> dict[str, Any]:
        principal = round(float(principal), 2)
        locked = await session.scalar(select(NatCompany).where(NatCompany.id == company.id).with_for_update())
        if locked is None:
            raise ValueError("Компания не найдена")
        loans = await cls._active_loans(session, locked.id, for_update=True)
        now = get_game_now()
        for loan in loans:
            cls._accrue(loan, now)
        if any(loan.status == "DEFAULTED" for loan in loans):
            raise ValueError("Новый кредит недоступен до погашения просроченного долга")
        active_debt = sum(float(x.remaining_debt) for x in loans if x.status in {"ACTIVE", "DEFAULTED"})
        from backend.natbirzha.services.company_service import CompanyService
        nav = await CompanyService.calculate_audited_nav(session, locked)
        quote = cls.quote(locked, active_debt, nav=nav)
        if not quote["eligible"]:
            raise ValueError(f"Кредиты открываются с {MIN_LOAN_LEVEL} уровня")
        if principal < MIN_PRINCIPAL or principal > quote["max_principal"]:
            raise ValueError(
                f"Сумма кредита должна быть от {MIN_PRINCIPAL:,.0f} до {quote['max_principal']:,.0f} cash"
            )
        current = cls._naive(now)
        loan = NatLoan(
            company_id=locked.id,
            principal=principal,
            remaining_debt=principal,
            daily_interest_rate=quote["daily_interest_rate"],
            due_date=(current + timedelta(days=LOAN_TERM_DAYS)).date(),
            status="ACTIVE",
            created_at=current,
            last_accrued_at=current,
        )
        session.add(loan)
        locked.cash = round(float(locked.cash) + principal, 2)
        await EconomyMetricsService.record(
            session, company_id=locked.id, flow="SOURCE", category="loan_principal",
            cash_amount=principal, context={"repayable": True},
        )
        await session.flush()
        return {"success": True, "cash_received": principal, "remaining_cash": locked.cash, "loan": cls.serialize(loan)}

    @classmethod
    async def repay(cls, session: AsyncSession, company: NatCompany, loan_id: int, amount: float) -> dict[str, Any]:
        amount = round(float(amount), 2)
        if amount <= 0:
            raise ValueError("Сумма погашения должна быть положительной")
        locked_company = await session.scalar(select(NatCompany).where(NatCompany.id == company.id).with_for_update())
        loan = await session.scalar(
            select(NatLoan).where(NatLoan.id == loan_id, NatLoan.company_id == company.id).with_for_update()
        )
        if locked_company is None or loan is None:
            raise ValueError("Кредит не найден")
        if loan.status not in {"ACTIVE", "DEFAULTED"}:
            raise ValueError("Кредит уже закрыт")
        cls._accrue(loan, get_game_now())
        payment = min(amount, float(loan.remaining_debt))
        if float(locked_company.cash) < payment:
            raise ValueError("Недостаточно cash для погашения")
        locked_company.cash = round(float(locked_company.cash) - payment, 2)
        loan.remaining_debt = round(float(loan.remaining_debt) - payment, 2)
        if loan.remaining_debt <= 0.01:
            loan.remaining_debt = 0.0
            loan.status = "PAID"
        await EconomyMetricsService.record(
            session, company_id=locked_company.id, flow="SINK", category="loan_repayment",
            cash_amount=payment, context={"loan_id": loan.id},
        )
        await session.flush()
        return {"success": True, "paid": payment, "remaining_cash": locked_company.cash, "loan": cls.serialize(loan)}

    @staticmethod
    def serialize(loan: NatLoan) -> dict[str, Any]:
        return {
            "id": loan.id,
            "principal": round(float(loan.principal), 2),
            "remaining_debt": round(float(loan.remaining_debt), 2),
            "daily_interest_pct": round(float(loan.daily_interest_rate) * 100, 3),
            "due_date": loan.due_date.isoformat(),
            "status": loan.status,
        }


__all__ = ["LoanService", "MIN_LOAN_LEVEL"]
