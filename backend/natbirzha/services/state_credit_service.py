"""Fixed simple-interest loans funded by the State Treasury."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import game_dt_iso, get_game_now, normalize_dt
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.state_credit import NatStateCreditLoan
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


STATE_CREDIT_INTEREST_RATE_PCT = 7.5
STATE_CREDIT_DAILY_RATE = STATE_CREDIT_INTEREST_RATE_PCT / 100


class StateCreditService:
    @staticmethod
    def _now(value: datetime | None) -> datetime:
        return normalize_dt(value or get_game_now())

    @staticmethod
    def _amount(value: float, field: str) -> float:
        try:
            amount = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be a positive number") from exc
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"{field} must be a positive number")
        amount = round(amount, 2)
        if amount <= 0:
            raise ValueError(f"{field} must be at least 0.01 cash")
        return amount

    @staticmethod
    def _term_days(value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("Term days must be a positive integer")
        try:
            term_days = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Term days must be a positive integer") from exc
        try:
            if float(value) != term_days:
                raise ValueError("Term days must be a positive integer")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Term days must be a positive integer") from exc
        if term_days <= 0:
            raise ValueError("Term days must be a positive integer")
        return term_days

    @staticmethod
    def _apply_default(loan: NatStateCreditLoan, now: datetime) -> None:
        if loan.status == "ACTIVE" and now > loan.due_at and loan.remaining_debt > 0:
            loan.status = "DEFAULTED"

    @staticmethod
    def serialize(loan: NatStateCreditLoan) -> dict[str, Any]:
        return {
            "id": loan.id,
            "principal": round(float(loan.principal), 2),
            "total_due": round(float(loan.total_due), 2),
            "remaining_debt": round(float(loan.remaining_debt), 2),
            "term_days": int(loan.term_days),
            "due_at": game_dt_iso(loan.due_at),
            "status": loan.status,
        }

    @classmethod
    async def request(
        cls,
        session: AsyncSession,
        company: NatCompany,
        principal: float,
        term_days: int,
        *,
        now: datetime | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        principal = cls._amount(principal, "Principal")
        term_days = cls._term_days(term_days)
        current = cls._now(now)
        try:
            due_at = current + timedelta(days=term_days)
            total_due = round(principal * (1 + STATE_CREDIT_DAILY_RATE * term_days), 2)
        except OverflowError as exc:
            raise ValueError("Term creates an unsupported repayment amount or due date") from exc
        if not math.isfinite(total_due):
            raise ValueError("Calculated repayment amount is out of range")

        # All State Treasury transactions lock Treasury before the company row.
        treasury: NatStateTreasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        locked_company = await session.scalar(
            select(NatCompany)
            .where(NatCompany.id == company.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked_company is None:
            raise ValueError("Company not found")
        if float(treasury.cash) < principal:
            raise ValueError("State Treasury has insufficient cash for this credit")

        loan = NatStateCreditLoan(
            company_id=locked_company.id,
            principal=principal,
            total_due=total_due,
            remaining_debt=total_due,
            term_days=term_days,
            due_at=due_at,
            status="ACTIVE",
            created_at=current,
        )
        treasury.cash = round(float(treasury.cash) - principal, 2)
        treasury.updated_at = current
        locked_company.cash = round(float(locked_company.cash) + principal, 2)
        session.add(loan)
        await EconomyMetricsService.record(
            session,
            company_id=locked_company.id,
            flow="SOURCE",
            category="state_credit_principal",
            cash_amount=principal,
            context={"repayable": True, "term_days": term_days},
        )
        await session.flush()
        result = {
            "success": True,
            "cash_received": principal,
            "loan": cls.serialize(loan),
            "treasury_cash": round(float(treasury.cash), 2),
            "remaining_cash": round(float(locked_company.cash), 2),
        }
        if commit:
            await session.commit()
        return result

    @classmethod
    async def status(
        cls,
        session: AsyncSession,
        company: NatCompany,
        *,
        now: datetime | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        current = cls._now(now)
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        locked_company = await session.scalar(
            select(NatCompany)
            .where(NatCompany.id == company.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked_company is None:
            raise ValueError("Company not found")
        loans = list((await session.execute(
            select(NatStateCreditLoan)
            .where(NatStateCreditLoan.company_id == locked_company.id)
            .order_by(NatStateCreditLoan.id.asc())
            .with_for_update()
        )).scalars().all())
        for loan in loans:
            cls._apply_default(loan, current)
        await session.flush()
        result = {
            "treasury_cash": round(float(treasury.cash), 2),
            "interest_rate_pct": STATE_CREDIT_INTEREST_RATE_PCT,
            "loans": [cls.serialize(loan) for loan in loans],
        }
        if commit:
            await session.commit()
        return result

    @classmethod
    async def repay(
        cls,
        session: AsyncSession,
        company: NatCompany,
        loan_id: int,
        amount: float,
        *,
        now: datetime | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        amount = cls._amount(amount, "Repayment")
        current = cls._now(now)
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        locked_company = await session.scalar(
            select(NatCompany)
            .where(NatCompany.id == company.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        loan = await session.scalar(
            select(NatStateCreditLoan)
            .where(
                NatStateCreditLoan.id == loan_id,
                NatStateCreditLoan.company_id == company.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked_company is None or loan is None:
            raise ValueError("State credit loan not found")
        if loan.status == "PAID" or loan.remaining_debt <= 0:
            raise ValueError("State credit loan is already closed")

        cls._apply_default(loan, current)
        payment = round(min(amount, float(loan.remaining_debt)), 2)
        if float(locked_company.cash) < payment:
            raise ValueError("Company has insufficient cash for repayment")

        locked_company.cash = round(float(locked_company.cash) - payment, 2)
        treasury.cash = round(float(treasury.cash) + payment, 2)
        treasury.updated_at = current
        loan.remaining_debt = round(max(0.0, float(loan.remaining_debt) - payment), 2)
        if loan.remaining_debt == 0:
            loan.status = "PAID"
        await EconomyMetricsService.record(
            session,
            company_id=locked_company.id,
            flow="SINK",
            category="state_credit_repayment",
            cash_amount=payment,
            context={"loan_id": loan.id},
        )
        await session.flush()
        result = {
            "success": True,
            "paid": payment,
            "loan": cls.serialize(loan),
            "treasury_cash": round(float(treasury.cash), 2),
            "remaining_cash": round(float(locked_company.cash), 2),
        }
        if commit:
            await session.commit()
        return result


__all__ = ["STATE_CREDIT_INTEREST_RATE_PCT", "StateCreditService"]
