"""Customer accounts and fee-backed company payments for NATBIRZHA 2.0."""

from datetime import datetime, timedelta
from math import isfinite
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import (
    NatNextGameCompany,
    NatNextGameFacility,
)
from backend.natbirzha.models.next_game_banking import (
    NatNextGameBankAccount,
    NatNextGameBankPayment,
    NatNextGameCorporateLoan,
)
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_service.common import _utcnow


ACCOUNT_SERVICE_BRANCHES = frozenset({
    "retail", "corporate", "digital_bank", "corporate_accounts",
    "branch_network", "merchant_acquiring", "atm_network",
})
MIN_PAYMENT = 100.0
MAX_PAYMENT = 10_000_000.0
BASE_FEE_BPS = 100
MIN_FEE_BPS = 25
MAX_FEE = 10_000.0
MIN_BUSINESS_LOAN = 1_000.0
MAX_BUSINESS_LOAN = 100_000.0
BUSINESS_LOAN_DAILY_RATE = 0.005
MAX_BUSINESS_LOAN_DAYS = 30
LENDING_BRANCHES = frozenset({"corporate", "branch_network"})


class NextGameBankingService:
    """Runs settlement-account transfers without creating or deleting cash."""

    @classmethod
    async def _service_facilities(
        cls, session: AsyncSession, bank_company_id: int,
    ) -> list[NatNextGameFacility]:
        return list((await session.scalars(
            select(NatNextGameFacility).where(
                NatNextGameFacility.company_id == int(bank_company_id),
                NatNextGameFacility.branch_id.in_(ACCOUNT_SERVICE_BRANCHES),
            ).order_by(NatNextGameFacility.level.desc(), NatNextGameFacility.id)
        )).all())

    @classmethod
    async def _provider(cls, session: AsyncSession, bank_company_id: int):
        bank = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.id == int(bank_company_id),
            NatNextGameCompany.sector_id == "bank",
        ))
        if bank is None:
            raise ValueError("Компания банка не найдена")
        facilities = await cls._service_facilities(session, bank.id)
        if not facilities:
            raise ValueError("Банк ещё не построил завод обслуживания счетов")
        return bank, facilities

    @staticmethod
    def _fee_bps(facilities: list[NatNextGameFacility]) -> int:
        best_level = max(int(row.level) for row in facilities)
        return max(MIN_FEE_BPS, BASE_FEE_BPS - max(0, best_level - 1) * 5)

    @classmethod
    async def open_account(
        cls, session: AsyncSession, owner_tg_id: int, bank_company_id: int,
    ) -> dict[str, Any]:
        await NextGameService._lock_treasury_for_sqlite(session)
        customer = await NextGameService._owned_company(session, owner_tg_id)
        bank, facilities = await cls._provider(session, bank_company_id)
        if customer.id == bank.id:
            raise ValueError("Нельзя открыть счёт компании в собственном банке")
        existing = await session.scalar(select(NatNextGameBankAccount).where(
            NatNextGameBankAccount.bank_company_id == bank.id,
            NatNextGameBankAccount.customer_company_id == customer.id,
        ).with_for_update())
        if existing is not None:
            if existing.status != "ACTIVE":
                existing.status = "ACTIVE"
                existing.closed_at = None
            await session.flush()
            return cls._account_payload(existing, bank, facilities)
        account = NatNextGameBankAccount(
            bank_company_id=bank.id,
            customer_company_id=customer.id,
            status="ACTIVE",
        )
        session.add(account)
        await session.flush()
        return cls._account_payload(account, bank, facilities)

    @classmethod
    async def transfer(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        bank_company_id: int,
        payee_company_id: int,
        amount: float,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        raw_amount = float(amount)
        if not isfinite(raw_amount):
            raise ValueError("Сумма платежа должна быть конечным числом")
        normalized_amount = round(raw_amount, 2)
        if abs(raw_amount - normalized_amount) > 1e-9:
            raise ValueError("Сумма платежа указывается максимум с двумя знаками")
        if normalized_amount < MIN_PAYMENT or normalized_amount > MAX_PAYMENT:
            raise ValueError("Сумма платежа должна быть от 100 до 10 000 000 cash")
        key = str(idempotency_key or "").strip()[:128]
        if not key:
            raise ValueError("Нужен ключ идемпотентности")

        # A shared SQLite write lock and ordered company locks prevent two
        # concurrent transfers from spending the same company cash twice.
        await NextGameService._lock_treasury_for_sqlite(session)
        (await session.scalars(
            select(NatNextGameCompany).order_by(NatNextGameCompany.id).with_for_update()
        )).all()
        payer = await NextGameService._owned_company(session, owner_tg_id)
        bank, facilities = await cls._provider(session, bank_company_id)
        payee = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.id == int(payee_company_id),
        ).with_for_update())
        if payee is None:
            raise ValueError("Компания-получатель не найдена")
        if payer.id == payee.id:
            raise ValueError("Нельзя переводить деньги своей же компании")
        if payer.id == bank.id or payee.id == bank.id:
            raise ValueError("Переводы между банком и его собственной компанией запрещены")

        prior = await session.scalar(select(NatNextGameBankPayment).where(
            NatNextGameBankPayment.bank_company_id == bank.id,
            NatNextGameBankPayment.idempotency_key == key,
        ))
        if prior is not None:
            if (prior.payer_company_id != payer.id
                    or prior.payee_company_id != payee.id
                    or round(float(prior.amount), 2) != normalized_amount):
                raise ValueError("Ключ идемпотентности уже использован для другого платежа")
            return cls._payment_payload(prior, payer, payee, bank)

        payer_account = await session.scalar(select(NatNextGameBankAccount).where(
            NatNextGameBankAccount.bank_company_id == bank.id,
            NatNextGameBankAccount.customer_company_id == payer.id,
            NatNextGameBankAccount.status == "ACTIVE",
        ).with_for_update())
        payee_account = await session.scalar(select(NatNextGameBankAccount).where(
            NatNextGameBankAccount.bank_company_id == bank.id,
            NatNextGameBankAccount.customer_company_id == payee.id,
            NatNextGameBankAccount.status == "ACTIVE",
        ).with_for_update())
        if payer_account is None or payee_account is None:
            raise ValueError("Для обеих компаний нужен активный расчётный счёт в этом банке")

        fee_bps = cls._fee_bps(facilities)
        fee = min(MAX_FEE, round(max(1.0, normalized_amount * fee_bps / 10_000), 2))
        total = round(normalized_amount + fee, 2)
        if float(payer.cash) + 1e-9 < total:
            raise ValueError("Недостаточно cash на платёж и банковскую комиссию")

        payer.cash = round(float(payer.cash) - total, 2)
        payee.cash = round(float(payee.cash) + normalized_amount, 2)
        bank.cash = round(float(bank.cash) + fee, 2)
        payment = NatNextGameBankPayment(
            bank_company_id=bank.id,
            payer_account_id=payer_account.id,
            payee_account_id=payee_account.id,
            payer_company_id=payer.id,
            payee_company_id=payee.id,
            amount=normalized_amount,
            fee=fee,
            idempotency_key=key,
            created_at=now or _utcnow(),
        )
        session.add(payment)
        await session.flush()
        return cls._payment_payload(payment, payer, payee, bank)

    @classmethod
    async def request_business_loan(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        bank_company_id: int,
        amount: float,
        term_days: int,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        raw_amount = float(amount)
        if not isfinite(raw_amount):
            raise ValueError("Сумма кредита должна быть конечным числом")
        principal = round(raw_amount, 2)
        if abs(raw_amount - principal) > 1e-9:
            raise ValueError("Сумму кредита можно указать максимум с двумя знаками")
        if principal < MIN_BUSINESS_LOAN or principal > MAX_BUSINESS_LOAN:
            raise ValueError("Сумма кредита должна быть от 1 000 до 100 000 cash")
        days = int(term_days)
        if days < 1 or days > MAX_BUSINESS_LOAN_DAYS:
            raise ValueError("Срок кредита должен быть от 1 до 30 дней")
        key = str(idempotency_key or "").strip()[:128]
        if not key:
            raise ValueError("Нужен ключ идемпотентности")

        await NextGameService._lock_treasury_for_sqlite(session)
        (await session.scalars(
            select(NatNextGameCompany).order_by(NatNextGameCompany.id).with_for_update()
        )).all()
        borrower = await NextGameService._owned_company(session, owner_tg_id)
        bank, facilities = await cls._provider(session, bank_company_id)
        if bank.id == borrower.id:
            raise ValueError("Банк не может кредитовать собственную компанию")
        if not any(row.branch_id in LENDING_BRANCHES for row in facilities):
            raise ValueError("Банк ещё не открыл корпоративное кредитование")

        previous = await session.scalar(select(NatNextGameCorporateLoan).where(
            NatNextGameCorporateLoan.bank_company_id == bank.id,
            NatNextGameCorporateLoan.idempotency_key == key,
        ))
        if previous is not None:
            if (previous.borrower_company_id != borrower.id
                    or round(float(previous.principal), 2) != principal
                    or int(previous.term_days) != days):
                raise ValueError("Ключ идемпотентности уже использован для другого кредита")
            return cls._loan_payload(previous, bank, borrower)

        active = await session.scalar(select(NatNextGameCorporateLoan.id).where(
            NatNextGameCorporateLoan.borrower_company_id == borrower.id,
            NatNextGameCorporateLoan.status == "ACTIVE",
        ).limit(1))
        if active is not None:
            raise ValueError("Сначала погасите активный кредит компании")
        account = await session.scalar(select(NatNextGameBankAccount.id).where(
            NatNextGameBankAccount.bank_company_id == bank.id,
            NatNextGameBankAccount.customer_company_id == borrower.id,
            NatNextGameBankAccount.status == "ACTIVE",
        ))
        if account is None:
            raise ValueError("Сначала откройте расчётный счёт в этом банке")
        lending_capacity = round(min(MAX_BUSINESS_LOAN, max(0.0, float(bank.cash) * 0.5)), 2)
        if principal > lending_capacity:
            raise ValueError(f"Превышен свободный лимит кредитования банка: {lending_capacity:,.2f} cash")
        current = now or _utcnow()
        maturity_amount = round(principal * (1 + BUSINESS_LOAN_DAILY_RATE * days), 2)
        loan = NatNextGameCorporateLoan(
            bank_company_id=bank.id,
            borrower_company_id=borrower.id,
            principal=principal,
            daily_rate=BUSINESS_LOAN_DAILY_RATE,
            term_days=days,
            maturity_amount=maturity_amount,
            status="ACTIVE",
            idempotency_key=key,
            issued_at=current,
            due_at=current + timedelta(days=days),
        )
        bank.cash = round(float(bank.cash) - principal, 2)
        borrower.cash = round(float(borrower.cash) + principal, 2)
        session.add(loan)
        await session.flush()
        return cls._loan_payload(loan, bank, borrower)

    @classmethod
    async def repay_business_loan(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        loan_id: int,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        key = str(idempotency_key or "").strip()[:128]
        if not key:
            raise ValueError("Нужен ключ идемпотентности")
        await NextGameService._lock_treasury_for_sqlite(session)
        (await session.scalars(
            select(NatNextGameCompany).order_by(NatNextGameCompany.id).with_for_update()
        )).all()
        borrower = await NextGameService._owned_company(session, owner_tg_id)
        loan = await session.scalar(select(NatNextGameCorporateLoan).where(
            NatNextGameCorporateLoan.id == int(loan_id),
            NatNextGameCorporateLoan.borrower_company_id == borrower.id,
        ).with_for_update())
        if loan is None:
            raise ValueError("Кредит компании не найден")
        bank = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.id == loan.bank_company_id,
        ).with_for_update())
        if bank is None:
            raise ValueError("Банк-кредитор не найден")
        if loan.status == "PAID":
            if loan.repayment_key == key:
                return {
                    "success": True,
                    "paid_amount": round(float(loan.repaid_amount or 0), 2),
                    "loan": cls._loan_payload(loan, bank, borrower)["loan"],
                }
            raise ValueError("Кредит уже погашен")

        current = now or _utcnow()
        elapsed_days = max(1, int((current - loan.issued_at).total_seconds() // 86_400))
        accrued_days = min(int(loan.term_days), elapsed_days)
        paid_amount = round(float(loan.principal) * (1 + float(loan.daily_rate) * accrued_days), 2)
        if float(borrower.cash) + 1e-9 < paid_amount:
            raise ValueError("Недостаточно cash для погашения кредита")
        borrower.cash = round(float(borrower.cash) - paid_amount, 2)
        bank.cash = round(float(bank.cash) + paid_amount, 2)
        loan.status = "PAID"
        loan.repayment_key = key
        loan.repaid_at = current
        loan.repaid_amount = paid_amount
        await session.flush()
        return {"success": True, "paid_amount": paid_amount, "loan": cls._loan_payload(loan, bank, borrower)["loan"]}

    @classmethod
    async def snapshot(cls, session: AsyncSession, company: NatNextGameCompany) -> dict[str, Any]:
        companies = list((await session.scalars(
            select(NatNextGameCompany).order_by(NatNextGameCompany.name, NatNextGameCompany.id)
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
        loan_rows = [
            cls._loan_payload(row, by_id.get(row.bank_company_id), by_id.get(row.borrower_company_id))["loan"]
            for row in loans
        ]
        loan_interest_income = await session.scalar(select(func.coalesce(func.sum(
            NatNextGameCorporateLoan.repaid_amount - NatNextGameCorporateLoan.principal
        ), 0.0)).where(
            NatNextGameCorporateLoan.bank_company_id == company.id,
            NatNextGameCorporateLoan.status == "PAID",
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
        if loan.status == "PAID":
            due_amount = round(float(loan.repaid_amount or loan.maturity_amount), 2)
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
                "status": loan.status,
                "issued_at": loan.issued_at.isoformat(),
                "due_at": loan.due_at.isoformat(),
                "repaid_at": loan.repaid_at.isoformat() if loan.repaid_at else None,
            },
        }


__all__ = ["NextGameBankingService", "MIN_PAYMENT", "MAX_PAYMENT"]
