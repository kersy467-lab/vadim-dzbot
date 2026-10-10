"""Escrowed, bilateral company loans for the isolated NATBIRZHA 2.0 game."""

from datetime import datetime, timedelta
from math import isfinite
from typing import Any

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_finance import NatNextGameFinanceContract
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_service.common import _utcnow


MIN_PRINCIPAL = 1_000.0
MAX_PRINCIPAL = 100_000.0
MAX_DAILY_RATE_BPS = 100  # 1% per 24 hours; simple interest, no compounding.
MAX_TERM_DAYS = 30


class NextGameFinanceContractService:
    """Creates direct loans where unaccepted principal stays reserved by debit."""

    @classmethod
    async def create_offer(
        cls,
        session: AsyncSession,
        lender_tg_id: int,
        borrower_company_id: int,
        principal: float,
        daily_rate_bps: int,
        term_days: int,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        amount = cls._money(principal, "Сумма займа")
        if amount < MIN_PRINCIPAL or amount > MAX_PRINCIPAL:
            raise ValueError("Сумма займа должна быть от 1 000 до 100 000 cash")
        rate = cls._integer(daily_rate_bps, "Ставка")
        if rate < 0 or rate > MAX_DAILY_RATE_BPS:
            raise ValueError("Ставка должна быть от 0 до 100 базисных пунктов за сутки")
        term = cls._integer(term_days, "Срок")
        if term < 1 or term > MAX_TERM_DAYS:
            raise ValueError("Срок займа должен быть от 1 до 30 дней")
        key = cls._key(idempotency_key)

        await cls._lock_companies(session)
        lender = await NextGameService._owned_company(session, lender_tg_id)
        borrower = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.id == int(borrower_company_id),
        ).with_for_update())
        if borrower is None:
            raise ValueError("Компания-заёмщик не найдена")
        if lender.id == borrower.id:
            raise ValueError("Нельзя выдать займ собственной компании")

        previous = await session.scalar(select(NatNextGameFinanceContract).where(
            NatNextGameFinanceContract.lender_company_id == lender.id,
            NatNextGameFinanceContract.offer_key == key,
        ))
        if previous is not None:
            if (previous.borrower_company_id != borrower.id
                    or round(float(previous.principal), 2) != amount
                    or int(previous.daily_rate_bps) != rate
                    or int(previous.term_days) != term):
                raise ValueError("Ключ предложения уже использован с другими условиями")
            return cls._payload(previous, lender, borrower, now=now)

        if float(lender.cash) + 1e-9 < amount:
            raise ValueError("Недостаточно cash для резервирования займа")
        current = now or _utcnow()
        daily_rate = rate / 10_000
        maturity = round(amount * (1 + daily_rate * term), 2)
        contract = NatNextGameFinanceContract(
            lender_company_id=lender.id,
            borrower_company_id=borrower.id,
            principal=amount,
            daily_rate_bps=rate,
            term_days=term,
            maturity_amount=maturity,
            status="OPEN",
            offer_key=key,
            offered_at=current,
        )
        lender.cash = round(float(lender.cash) - amount, 2)
        session.add(contract)
        await session.flush()
        session.add(NextGameService._ledger(
            lender.id, "DIRECT_LOAN_ESCROW", -amount, amount,
            metadata={"borrower_company_id": borrower.id, "contract_id": contract.id},
        ))
        await session.flush()
        return cls._payload(contract, lender, borrower, now=current)

    @classmethod
    async def accept_offer(
        cls,
        session: AsyncSession,
        borrower_tg_id: int,
        contract_id: int,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        key = cls._key(idempotency_key)
        await cls._lock_companies(session)
        borrower = await NextGameService._owned_company(session, borrower_tg_id)
        contract = await session.scalar(select(NatNextGameFinanceContract).where(
            NatNextGameFinanceContract.id == int(contract_id),
            NatNextGameFinanceContract.borrower_company_id == borrower.id,
        ).with_for_update())
        if contract is None:
            raise ValueError("Предложение займа для этой компании не найдено")
        lender = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.id == contract.lender_company_id,
        ).with_for_update())
        if lender is None:
            raise ValueError("Компания-кредитор не найдена")
        if contract.status == "ACTIVE" and contract.accept_key == key:
            return cls._payload(contract, lender, borrower, now=now)
        if contract.status == "ACTIVE":
            raise ValueError("Предложение уже принято; сначала погасите активный займ")
        if contract.status != "OPEN":
            raise ValueError("Предложение уже принято, отменено или закрыто")
        active = await session.scalar(select(NatNextGameFinanceContract.id).where(
            NatNextGameFinanceContract.borrower_company_id == borrower.id,
            NatNextGameFinanceContract.status == "ACTIVE",
        ).limit(1))
        if active is not None:
            raise ValueError("Сначала погасите активный займ")

        current = now or _utcnow()
        borrower.cash = round(float(borrower.cash) + float(contract.principal), 2)
        contract.status = "ACTIVE"
        contract.accept_key = key
        contract.accepted_at = current
        contract.due_at = current + timedelta(days=int(contract.term_days))
        session.add(NextGameService._ledger(
            borrower.id, "DIRECT_LOAN_DISBURSED", float(contract.principal),
            -float(contract.principal),
            metadata={"lender_company_id": lender.id, "contract_id": contract.id},
        ))
        await session.flush()
        return cls._payload(contract, lender, borrower, now=current)

    @classmethod
    async def cancel_offer(
        cls,
        session: AsyncSession,
        lender_tg_id: int,
        contract_id: int,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        key = cls._key(idempotency_key)
        await cls._lock_companies(session)
        lender = await NextGameService._owned_company(session, lender_tg_id)
        contract = await session.scalar(select(NatNextGameFinanceContract).where(
            NatNextGameFinanceContract.id == int(contract_id),
            NatNextGameFinanceContract.lender_company_id == lender.id,
        ).with_for_update())
        if contract is None:
            raise ValueError("Предложение займа не найдено")
        borrower = await session.get(NatNextGameCompany, contract.borrower_company_id)
        if contract.status == "CANCELLED" and contract.cancel_key == key:
            return cls._payload(contract, lender, borrower)
        if contract.status != "OPEN":
            raise ValueError("Можно отменить только ещё не принятое предложение")
        principal = round(float(contract.principal), 2)
        lender.cash = round(float(lender.cash) + principal, 2)
        contract.status = "CANCELLED"
        contract.cancel_key = key
        session.add(NextGameService._ledger(
            lender.id, "DIRECT_LOAN_CANCELLED", principal, -principal,
            metadata={"borrower_company_id": contract.borrower_company_id, "contract_id": contract.id},
        ))
        await session.flush()
        return cls._payload(contract, lender, borrower)

    @classmethod
    async def repay_loan(
        cls,
        session: AsyncSession,
        borrower_tg_id: int,
        contract_id: int,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        key = cls._key(idempotency_key)
        await cls._lock_companies(session)
        borrower = await NextGameService._owned_company(session, borrower_tg_id)
        contract = await session.scalar(select(NatNextGameFinanceContract).where(
            NatNextGameFinanceContract.id == int(contract_id),
            NatNextGameFinanceContract.borrower_company_id == borrower.id,
        ).with_for_update())
        if contract is None:
            raise ValueError("Займ компании не найден")
        lender = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.id == contract.lender_company_id,
        ).with_for_update())
        if lender is None:
            raise ValueError("Компания-кредитор не найдена")
        if contract.status == "PAID":
            if contract.repayment_key == key:
                return {
                    "success": True,
                    "paid_amount": round(float(contract.repaid_amount or 0), 2),
                    "contract": cls._payload(contract, lender, borrower)["contract"],
                }
            raise ValueError("Займ уже погашен")
        if contract.status != "ACTIVE" or contract.accepted_at is None:
            raise ValueError("Можно погасить только принятый займ")

        current = now or _utcnow()
        elapsed = max(1, int((current - contract.accepted_at).total_seconds() // 86_400))
        accrued = min(int(contract.term_days), elapsed)
        daily_rate = int(contract.daily_rate_bps) / 10_000
        paid_amount = round(float(contract.principal) * (1 + daily_rate * accrued), 2)
        if float(borrower.cash) + 1e-9 < paid_amount:
            raise ValueError("Недостаточно cash для погашения займа")
        borrower.cash = round(float(borrower.cash) - paid_amount, 2)
        lender.cash = round(float(lender.cash) + paid_amount, 2)
        contract.status = "PAID"
        contract.repayment_key = key
        contract.repaid_at = current
        contract.repaid_amount = paid_amount
        session.add(NextGameService._ledger(
            borrower.id, "DIRECT_LOAN_REPAY", -paid_amount, paid_amount,
            metadata={"lender_company_id": lender.id, "contract_id": contract.id},
        ))
        session.add(NextGameService._ledger(
            lender.id, "DIRECT_LOAN_REPAY", paid_amount, -paid_amount,
            metadata={"borrower_company_id": borrower.id, "contract_id": contract.id},
        ))
        await session.flush()
        return {"success": True, "paid_amount": paid_amount,
                "contract": cls._payload(contract, lender, borrower, now=current)["contract"]}

    @classmethod
    async def snapshot(cls, session: AsyncSession, company: NatNextGameCompany) -> dict[str, Any]:
        rows = list((await session.scalars(select(NatNextGameFinanceContract).where(
            (NatNextGameFinanceContract.lender_company_id == company.id)
            | (NatNextGameFinanceContract.borrower_company_id == company.id)
        ).order_by(case(
            (NatNextGameFinanceContract.status.in_(("OPEN", "ACTIVE")), 0), else_=1,
        ), NatNextGameFinanceContract.offered_at.desc(),
                   NatNextGameFinanceContract.id.desc()).limit(24))).all())
        related_ids = {row.lender_company_id for row in rows} | {row.borrower_company_id for row in rows}
        companies = list((await session.scalars(select(NatNextGameCompany).where(
            NatNextGameCompany.id.in_(related_ids or {company.id}),
        ))).all())
        by_id = {row.id: row for row in companies}
        current = _utcnow()
        contracts = [cls._payload(
            row, by_id.get(row.lender_company_id), by_id.get(row.borrower_company_id), now=current,
        )["contract"] for row in rows]
        open_bids = [row for row in contracts if row["status"] == "OPEN" and row["borrower_company_id"] == company.id]
        open_offers = [row for row in contracts if row["status"] == "OPEN" and row["lender_company_id"] == company.id]
        active = [row for row in contracts if row["status"] in {"ACTIVE", "OVERDUE"}]
        return {
            "contracts": contracts,
            "open_incoming": open_bids,
            "open_outgoing": open_offers,
            "active": active,
        }

    @classmethod
    def _payload(cls, contract, lender, borrower, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or _utcnow()
        daily_rate = int(contract.daily_rate_bps) / 10_000
        if contract.status == "PAID":
            due_amount = round(float(contract.repaid_amount or contract.maturity_amount), 2)
        elif contract.status == "ACTIVE" and contract.accepted_at is not None:
            elapsed = max(1, int((current - contract.accepted_at).total_seconds() // 86_400))
            due_amount = round(float(contract.principal) * (
                1 + daily_rate * min(int(contract.term_days), elapsed)
            ), 2)
        else:
            due_amount = round(float(contract.maturity_amount), 2)
        status = contract.status
        if status == "ACTIVE" and contract.due_at and current > contract.due_at:
            status = "OVERDUE"
        return {"contract": {
            "id": int(contract.id),
            "lender_company_id": int(contract.lender_company_id),
            "lender_name": getattr(lender, "name", "Компания-кредитор"),
            "borrower_company_id": int(contract.borrower_company_id),
            "borrower_name": getattr(borrower, "name", "Компания-заёмщик"),
            "principal": round(float(contract.principal), 2),
            "daily_rate_bps": int(contract.daily_rate_bps),
            "daily_rate_percent": round(daily_rate * 100, 2),
            "term_days": int(contract.term_days),
            "maturity_amount": round(float(contract.maturity_amount), 2),
            "due_amount": due_amount,
            "status": status,
            "offered_at": contract.offered_at.isoformat(),
            "accepted_at": contract.accepted_at.isoformat() if contract.accepted_at else None,
            "due_at": contract.due_at.isoformat() if contract.due_at else None,
            "repaid_at": contract.repaid_at.isoformat() if contract.repaid_at else None,
        }}

    @classmethod
    async def _lock_companies(cls, session: AsyncSession) -> None:
        await NextGameService._lock_treasury_for_sqlite(session)
        (await session.scalars(
            select(NatNextGameCompany).order_by(NatNextGameCompany.id).with_for_update()
        )).all()

    @staticmethod
    def _money(value: float, label: str) -> float:
        raw = float(value)
        if not isfinite(raw):
            raise ValueError(f"{label} должна быть конечным числом")
        rounded = round(raw, 2)
        if abs(raw - rounded) > 1e-9:
            raise ValueError(f"{label}: максимум два знака после запятой")
        return rounded

    @staticmethod
    def _integer(value: int, label: str) -> int:
        try:
            integer = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{label} должна быть целым числом") from exc
        if isinstance(value, bool) or float(value) != integer:
            raise ValueError(f"{label} должна быть целым числом")
        return integer

    @staticmethod
    def _key(value: str) -> str:
        key = str(value or "").strip()[:128]
        if not key:
            raise ValueError("Нужен ключ идемпотентности")
        return key


__all__ = [
    "NextGameFinanceContractService", "MIN_PRINCIPAL", "MAX_PRINCIPAL",
    "MAX_DAILY_RATE_BPS", "MAX_TERM_DAYS",
]
