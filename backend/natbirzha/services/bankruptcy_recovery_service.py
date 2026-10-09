"""Shared loan write-off and fresh-start behavior after company bankruptcy."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.contracts import NatLoan
from backend.natbirzha.models.state_credit import NatStateCreditLoan


RESTART_CASH_GRANT = 100_000.0


class BankruptcyRecoveryService:
    @staticmethod
    async def forgive_open_loans(session: AsyncSession, company_id: int) -> dict[str, float | int]:
        """Remove company debts and cancel pending state-credit applications."""
        loans = list((await session.execute(
            select(NatLoan)
            .where(
                NatLoan.company_id == company_id,
                NatLoan.status.in_(("ACTIVE", "DEFAULTED")),
            )
            .with_for_update()
        )).scalars().all())
        state_loans = list((await session.execute(
            select(NatStateCreditLoan)
            .where(
                NatStateCreditLoan.company_id == company_id,
                NatStateCreditLoan.status.in_(("PENDING", "ACTIVE", "DEFAULTED")),
            )
            .with_for_update()
        )).scalars().all())

        debt_written_off = 0.0
        for loan in loans:
            debt_written_off += max(0.0, float(loan.remaining_debt or 0.0))
            loan.remaining_debt = 0.0
            loan.status = "FORGIVEN"

        loans_forgiven = 0
        pending_cancelled = 0
        for loan in state_loans:
            if loan.status == "PENDING":
                loan.status = "CANCELLED"
                pending_cancelled += 1
            else:
                debt_written_off += max(0.0, float(loan.remaining_debt or 0.0))
                loan.status = "FORGIVEN"
                loans_forgiven += 1
            loan.remaining_debt = 0.0

        await session.flush()
        return {
            "loans_forgiven": loans_forgiven + len(loans),
            "pending_cancelled": pending_cancelled,
            "debt_written_off": round(debt_written_off, 2),
        }

    @staticmethod
    async def restart_company(
        session: AsyncSession,
        company: NatCompany,
        *,
        commit: bool = True,
    ) -> NatCompany:
        """Replace a bankrupt company with a new level-one company and a cash grant."""
        if not company.is_bankrupt:
            raise ValueError("Начать заново с бонусом можно только после банкротства.")

        owner_id = int(company.user_id)
        name = str(company.name)
        specialization = str(company.specialization)
        ticker = company.custom_ticker
        pvc_balance = int(company.pvc_balance or 0)
        nat_balance = int(company.nat_balance or 0)

        from backend.natbirzha.services.company_service import CompanyService

        removed = await CompanyService.reset_company_for_user(
            session, owner_id, commit=False,
        )
        if not removed:
            raise ValueError("Компания для перезапуска не найдена.")

        restarted = await CompanyService.create_company(
            session, owner_id, name, specialization, ticker=ticker, commit=False,
        )
        restarted.cash = round(float(restarted.cash or 0.0) + RESTART_CASH_GRANT, 2)
        restarted.nat_balance = nat_balance
        pvc_delta = pvc_balance - int(restarted.pvc_balance or 0)
        if pvc_delta:
            from backend.natbirzha.services.premium_service import PremiumService

            await PremiumService.apply_pvc(
                session,
                restarted.id,
                pvc_delta,
                "bankruptcy_reset_transfer",
                f"bankruptcy_reset_pvc_{company.id}_{restarted.id}",
                metadata={"source_company_id": int(company.id)},
            )
        await session.flush()

        if commit:
            await session.commit()
            await session.refresh(restarted)
        return restarted


__all__ = ["BankruptcyRecoveryService", "RESTART_CASH_GRANT"]
