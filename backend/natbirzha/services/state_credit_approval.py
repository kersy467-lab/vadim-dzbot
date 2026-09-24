"""Approval, limit enforcement and Treasury credit checks."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.models.state_credit import NatStateCreditLoan
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService
from backend.natbirzha.services.state_credit_rules import (
    STATE_CREDIT_DAILY_RATE,
    STATE_CREDIT_MAX_NAV_PCT,
    STATE_CREDIT_OPEN_STATUSES,
)


class StateCreditApprovalMixin:
    @staticmethod
    async def _open_principal(
        session: AsyncSession, company_id: int, *, exclude_loan_id: int | None = None
    ) -> float:
        query = select(func.coalesce(func.sum(NatStateCreditLoan.principal), 0.0)).where(
            NatStateCreditLoan.company_id == company_id,
            NatStateCreditLoan.status.in_(STATE_CREDIT_OPEN_STATUSES),
        )
        if exclude_loan_id is not None:
            query = query.where(NatStateCreditLoan.id != exclude_loan_id)
        return round(float(await session.scalar(query) or 0.0), 2)

    @classmethod
    async def _available_limit(
        cls, session: AsyncSession, company: NatCompany, *, exclude_loan_id: int | None = None
    ) -> tuple[float, float, float]:
        nav = await CompanyService.calculate_audited_nav(session, company)
        limit = round(max(0.0, nav) * STATE_CREDIT_MAX_NAV_PCT / 100, 2)
        booked = await cls._open_principal(
            session, company.id, exclude_loan_id=exclude_loan_id
        )
        return nav, limit, round(max(0.0, limit - booked), 2)

    @classmethod
    async def decide(
        cls,
        session: AsyncSession,
        loan_id: int,
        *,
        actor_id: int,
        approved: bool,
        now: datetime | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        current = cls._now(now)
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        initial = await session.get(NatStateCreditLoan, loan_id)
        if initial is None:
            raise ValueError("State credit request not found")
        company = await session.scalar(
            select(NatCompany)
            .where(NatCompany.id == initial.company_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        loan = await session.scalar(
            select(NatStateCreditLoan)
            .where(NatStateCreditLoan.id == loan_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if company is None or loan is None:
            raise ValueError("State credit request not found")
        if loan.status != "PENDING":
            raise ValueError("State credit request has already been reviewed")

        cash_received = 0.0
        if approved:
            nav, limit, available = await cls._available_limit(
                session, company, exclude_loan_id=loan.id
            )
            if float(loan.principal) > available + 1e-9:
                raise ValueError(
                    f"Approval exceeds the current 50% company-value credit limit. "
                    f"Available: {available:.2f} cash (NAV {nav:.2f}, limit {limit:.2f})."
                )
            if float(treasury.cash) < float(loan.principal):
                raise ValueError("State Treasury has insufficient cash for this credit")
            loan.total_due = round(
                float(loan.principal) * (1 + STATE_CREDIT_DAILY_RATE * int(loan.term_days)), 2
            )
            loan.remaining_debt = loan.total_due
            loan.due_at = current + timedelta(days=int(loan.term_days))
            loan.status = "ACTIVE"
            treasury.cash = round(float(treasury.cash) - float(loan.principal), 2)
            treasury.updated_at = current
            company.cash = round(float(company.cash) + float(loan.principal), 2)
            cash_received = round(float(loan.principal), 2)
            await EconomyMetricsService.record(
                session,
                company_id=company.id,
                flow="SOURCE",
                category="state_credit_principal",
                cash_amount=cash_received,
                context={"repayable": True, "term_days": int(loan.term_days)},
            )
        else:
            loan.status = "REJECTED"
            loan.remaining_debt = 0.0

        loan.reviewed_by = actor_id
        loan.reviewed_at = current
        session.add(NatCreatorAuditLog(
            actor_id=actor_id,
            action="STATE_CREDIT_APPROVED" if approved else "STATE_CREDIT_REJECTED",
            target_type="state_credit",
            target_id=str(loan.id),
            details=(
                f"Заявка компании {company.name}: principal {loan.principal} cash, "
                f"срок {loan.term_days} дн.; решение: {'одобрена' if approved else 'отклонена'}."
            ),
            created_at=current,
        ))
        await session.flush()
        result = {
            "success": True,
            "cash_received": cash_received,
            "loan": cls.serialize(loan),
            "treasury_cash": round(float(treasury.cash), 2),
            "remaining_cash": round(float(company.cash), 2),
        }
        if commit:
            await session.commit()
        return result

    @staticmethod
    async def has_open_credit(session: AsyncSession, company_id: int) -> bool:
        count = await session.scalar(
            select(func.count(NatStateCreditLoan.id)).where(
                NatStateCreditLoan.company_id == company_id,
                NatStateCreditLoan.status.in_(("ACTIVE", "DEFAULTED")),
                NatStateCreditLoan.remaining_debt > 0,
            )
        )
        return bool(count)

    @classmethod
    async def creator_requests(
        cls, session: AsyncSession, status: str = "PENDING"
    ) -> dict[str, Any]:
        normalized = status.strip().upper()
        if normalized not in {"PENDING", "ALL"}:
            raise ValueError("Status must be PENDING or ALL")
        statement = (
            select(NatStateCreditLoan, NatCompany)
            .join(NatCompany, NatCompany.id == NatStateCreditLoan.company_id)
            .order_by(NatStateCreditLoan.created_at.asc(), NatStateCreditLoan.id.asc())
        )
        if normalized == "PENDING":
            statement = statement.where(NatStateCreditLoan.status == "PENDING")
        rows = (await session.execute(statement)).all()
        requests = []
        for loan, company in rows:
            nav, limit, available = await cls._available_limit(
                session, company, exclude_loan_id=loan.id
            )
            requests.append({
                **cls.serialize(loan),
                "company_id": company.id,
                "company_name": company.name,
                "company_nav": nav,
                "credit_limit": limit,
                "other_open_principal": round(max(0.0, limit - available), 2),
            })
        return {"requests": requests}



__all__ = ["StateCreditApprovalMixin"]
