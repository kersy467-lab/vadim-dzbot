"""Bank account, loan and loss audit read projections."""
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_banking import NatNextGameBankAccount, NatNextGameBankPayment, NatNextGameCorporateLoan
from backend.natbirzha.models.next_game_bankruptcy import NatNextGameDebtWriteoff
from backend.natbirzha.services.next_game_service.common import _utcnow


class NextGameBankingReadMixin:
    @classmethod
    async def snapshot(cls, session: AsyncSession, company: NatNextGameCompany) -> dict[str, Any]:
        from backend.natbirzha.services.next_game_banking_service import (
            LENDING_BRANCHES, MAX_BUSINESS_LOAN, BUSINESS_LOAN_DAILY_RATE,
        )
        companies = list((await session.scalars(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id > 0).order_by(NatNextGameCompany.name, NatNextGameCompany.id)
        )).all())
        by_id = {row.id: row for row in companies}
        providers = []
        for bank in companies:
            if bank.sector_id != "bank":
                continue
            facilities = await cls._service_facilities(session, bank.id)
            if facilities:
                providers.append({
                    "bank_company_id": bank.id,
                    "bank_name": bank.name,
                    "fee_bps": cls._fee_bps(facilities),
                    "fee_percent": round(cls._fee_bps(facilities) / 100, 2),
                    "branches": [row.branch_id for row in facilities],
                })
        accounts = list((await session.scalars(
            select(NatNextGameBankAccount).where(
                NatNextGameBankAccount.customer_company_id == company.id,
                NatNextGameBankAccount.status == "ACTIVE",
            ).order_by(NatNextGameBankAccount.opened_at.desc(), NatNextGameBankAccount.id.desc())
        )).all())
        account_rows = []
        for account in accounts:
            bank = by_id.get(account.bank_company_id)
            provider = next((item for item in providers if item["bank_company_id"] == account.bank_company_id), None)
            account_rows.append({
                "id": account.id,
                "bank_company_id": account.bank_company_id,
                "bank_name": bank.name if bank else "Банк закрыт",
                "fee_bps": provider["fee_bps"] if provider else None,
                "opened_at": account.opened_at.isoformat(),
            })
        payments = list((await session.scalars(
            select(NatNextGameBankPayment).where(
                (NatNextGameBankPayment.payer_company_id == company.id)
                | (NatNextGameBankPayment.payee_company_id == company.id)
                | (NatNextGameBankPayment.bank_company_id == company.id)
            ).order_by(NatNextGameBankPayment.created_at.desc(), NatNextGameBankPayment.id.desc()).limit(12)
        )).all())
        payment_rows = [
            cls._payment_payload(row, by_id.get(row.payer_company_id),
                                 by_id.get(row.payee_company_id),
                                 by_id.get(row.bank_company_id))["payment"]
            for row in payments
        ]
        customer_count = await session.scalar(select(func.count(NatNextGameBankAccount.id)).where(
            NatNextGameBankAccount.bank_company_id == company.id,
            NatNextGameBankAccount.status == "ACTIVE",
        )) or 0
        fee_income = await session.scalar(select(func.coalesce(func.sum(NatNextGameBankPayment.fee), 0.0)).where(
            NatNextGameBankPayment.bank_company_id == company.id,
        )) or 0.0
        loans = list((await session.scalars(
            select(NatNextGameCorporateLoan).where(
                (NatNextGameCorporateLoan.borrower_company_id == company.id)
                | (NatNextGameCorporateLoan.bank_company_id == company.id)
            ).order_by(NatNextGameCorporateLoan.issued_at.desc(), NatNextGameCorporateLoan.id.desc()).limit(12)
        )).all())
        writeoffs = dict((await session.execute(select(NatNextGameDebtWriteoff.obligation_id,
            NatNextGameDebtWriteoff.amount).where(NatNextGameDebtWriteoff.kind == "CORPORATE_LOAN",
            NatNextGameDebtWriteoff.obligation_id.in_([row.id for row in loans])))).all())
        for row in loans:
            row._writeoff_amount = writeoffs.get(row.id)
        loan_rows = [
            cls._loan_payload(row, by_id.get(row.bank_company_id), by_id.get(row.borrower_company_id))["loan"]
            for row in loans
        ]
        loan_interest_income = await session.scalar(select(func.coalesce(func.sum(
            NatNextGameCorporateLoan.repaid_amount - NatNextGameCorporateLoan.principal
        ), 0.0)).where(
            NatNextGameCorporateLoan.bank_company_id == company.id,
            NatNextGameCorporateLoan.status == "PAID",
            ~NatNextGameCorporateLoan.id.in_(select(NatNextGameDebtWriteoff.obligation_id).where(
                NatNextGameDebtWriteoff.kind == "CORPORATE_LOAN")),
        )) or 0.0
        loan_offers = []
        for bank in companies:
            if bank.id == company.id or bank.sector_id != "bank":
                continue
            facilities = await cls._service_facilities(session, bank.id)
            if any(row.branch_id in LENDING_BRANCHES for row in facilities):
                loan_offers.append({
                    "bank_company_id": bank.id,
                    "bank_name": bank.name,
                    "max_amount": round(min(MAX_BUSINESS_LOAN, max(0.0, float(bank.cash) * 0.5)), 2),
                    "daily_rate": BUSINESS_LOAN_DAILY_RATE,
                })
        return {
            "providers": providers,
            "accounts": account_rows,
            "companies": [{"id": row.id, "name": row.name} for row in companies if row.id != company.id],
            "payments": payment_rows,
            "loans": loan_rows,
            "loan_offers": loan_offers,
            "bank_summary": {
                "customer_accounts": int(customer_count),
                "fee_income": round(float(fee_income), 2),
                "loan_interest_income": round(float(loan_interest_income), 2),
                "loans_outstanding": sum(
                    round(float(row.principal), 2) for row in loans
                    if row.bank_company_id == company.id and row.status == "ACTIVE"
                ),
            },
        }

    @classmethod
    def _account_payload(cls, account, bank, facilities) -> dict[str, Any]:
        fee_bps = cls._fee_bps(facilities)
        return {
            "success": True,
            "account": {
                "id": int(account.id),
                "bank_company_id": int(bank.id),
                "bank_name": bank.name,
                "status": account.status,
                "fee_bps": fee_bps,
                "fee_percent": round(fee_bps / 100, 2),
            },
        }

    @staticmethod
    def _payment_payload(payment, payer, payee, bank) -> dict[str, Any]:
        return {
            "success": True,
            "payment": {
                "id": int(payment.id),
                "bank_company_id": int(payment.bank_company_id),
                "bank_name": getattr(bank, "name", "Банк"),
                "payer_company_id": int(payment.payer_company_id),
                "payer_name": getattr(payer, "name", "Компания"),
                "payee_company_id": int(payment.payee_company_id),
                "payee_name": getattr(payee, "name", "Компания"),
                "amount": round(float(payment.amount), 2),
                "fee": round(float(payment.fee), 2),
                "total_paid": round(float(payment.amount) + float(payment.fee), 2),
                "created_at": payment.created_at.isoformat(),
            },
        }

    @staticmethod
    def _loan_payload(loan, bank, borrower) -> dict[str, Any]:
        current = _utcnow()
        written_off = getattr(loan, "_writeoff_amount", None) is not None
        if written_off:
            due_amount = 0.0
        elif loan.status == "PAID":
            due_amount = round(float(loan.repaid_amount if loan.repaid_amount is not None else loan.maturity_amount), 2)
        else:
            elapsed_days = max(1, int((current - loan.issued_at).total_seconds() // 86_400))
            accrued_days = min(int(loan.term_days), elapsed_days)
            due_amount = round(float(loan.principal) * (1 + float(loan.daily_rate) * accrued_days), 2)
        return {
            "success": True,
            "loan": {
                "id": int(loan.id),
                "bank_company_id": int(loan.bank_company_id),
                "bank_name": getattr(bank, "name", "Банк"),
                "borrower_company_id": int(loan.borrower_company_id),
                "borrower_name": getattr(borrower, "name", "Компания"),
                "principal": round(float(loan.principal), 2),
                "daily_rate": float(loan.daily_rate),
                "term_days": int(loan.term_days),
                "maturity_amount": round(float(loan.maturity_amount), 2),
                "due_amount": due_amount,
                "status": "WRITTEN_OFF" if written_off else loan.status,
                "paid_amount": float(loan.repaid_amount or 0),
                "written_off_amount": float(getattr(loan, "_writeoff_amount", None) or 0),
                "issued_at": loan.issued_at.isoformat(),
                "due_at": loan.due_at.isoformat(),
                "repaid_at": loan.repaid_at.isoformat() if loan.repaid_at else None,
            },
        }

