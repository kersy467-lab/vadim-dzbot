"""NPC market, credit and term-deposit operations for NATBIRZHA 2.0."""
from datetime import datetime, timedelta
from math import ceil, isfinite
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameDeposit, NatNextGameLoan, NatNextGameTreasury,
)
from backend.natbirzha.next_game_catalog import get_next_game_items
from .common import (
    BANK_DEPOSIT_DAILY_RATE, BANK_LOAN_DAILY_RATE, BUY_MARKUP, SELL_MARKDOWN,
    MAX_TRADE_QUANTITY, MAX_INVENTORY_PER_ITEM, MIN_BANK_LOAN, MAX_BANK_LOAN,
    MAX_BANK_LOAN_DAYS, MIN_BANK_DEPOSIT, MAX_BANK_DEPOSIT, MAX_BANK_DEPOSIT_DAYS,
    _utcnow,
)

class NextGameFinanceMixin:
    @classmethod
    async def trade(
        cls, session: AsyncSession, owner_tg_id: int, item_id: str,
        side: str, quantity: float, *, now: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_side = str(side or "").upper()
        amount = float(quantity)
        items = get_next_game_items()
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError("Выберите покупку или продажу")
        if item_id not in items:
            raise ValueError("Такого товара нет в рынке 2.0")
        if not isfinite(amount):
            raise ValueError("Количество должно быть конечное число")
        rounded_amount = round(amount, 4)
        if abs(amount - rounded_amount) > 1e-9:
            raise ValueError("Количество можно указать максимум с 4 знаками после запятой")
        amount = rounded_amount
        if amount <= 0 or amount > MAX_TRADE_QUANTITY:
            raise ValueError("Количество должно быть больше нуля и не выше 10 000")
        await cls._lock_treasury_for_sqlite(session)
        await cls.settle_company(session, owner_tg_id, now=now)
        company = await cls._owned_company(session, owner_tg_id)
        treasury = await cls._treasury(session)
        stock = dict(treasury.inventory_json or {})
        base = float(items[item_id]["base_price"])
        unit_price = round(base * (BUY_MARKUP if normalized_side == "BUY" else SELL_MARKDOWN), 2)
        total = round(amount * unit_price, 2)
        if total < 0.01:
            raise ValueError("Сумма сделки должна быть не меньше 0,01 cash")
        inventory = await cls._inventory_row(session, company.id, item_id)
        if normalized_side == "BUY":
            available = float(stock.get(item_id, 0.0))
            if available + 1e-9 < amount:
                raise ValueError("В резерве 2.0 недостаточно товара")
            own_quantity = float(inventory.quantity if inventory else 0.0)
            from backend.natbirzha.services.next_game_market_service import NextGameMarketService

            reserved_sell = await NextGameMarketService.reserved_sell_quantity(
                session, company.id, item_id,
            )
            if own_quantity + reserved_sell + amount > MAX_INVENTORY_PER_ITEM + 1e-9:
                raise ValueError("На складе 2.0 нет места для такого количества")
            if float(company.cash) + 1e-9 < total:
                raise ValueError("Недостаточно cash на покупку")
            company.cash = round(float(company.cash) - total, 2)
            treasury.cash = round(float(treasury.cash) + total, 2)
            stock[item_id] = round(available - amount, 4)
            await cls._change_inventory(session, company.id, item_id, amount, row=inventory)
            company_delta, treasury_delta = -total, total
            company_quantity, treasury_quantity = amount, -amount
        else:
            available = float(inventory.quantity if inventory else 0.0)
            if available + 1e-9 < amount:
                raise ValueError("Недостаточно товара на складе 2.0")
            if await cls._available_treasury_cash(session, treasury) + 1e-9 < total:
                raise ValueError("В казне 2.0 недостаточно свободных средств для скупки")
            company.cash = round(float(company.cash) + total, 2)
            treasury.cash = round(float(treasury.cash) - total, 2)
            stock[item_id] = round(float(stock.get(item_id, 0.0)) + amount, 4)
            await cls._change_inventory(session, company.id, item_id, -amount, row=inventory)
            company_delta, treasury_delta = total, -total
            company_quantity, treasury_quantity = -amount, amount
        treasury.inventory_json = stock
        session.add(cls._ledger(
            company.id, normalized_side, company_delta, treasury_delta, item_id=item_id,
            company_quantity=company_quantity, treasury_quantity=treasury_quantity,
            metadata={"quantity": amount, "unit_price": unit_price},
        ))
        await session.flush()
        return {
            "success": True, "side": normalized_side, "item_id": item_id,
            "quantity": amount, "unit_price": unit_price, "total": total,
            "cash_delta": company_delta, "company": cls.snapshot_company(company),
        }

    @classmethod
    async def request_bank_loan(
        cls, session: AsyncSession, owner_tg_id: int, amount: float,
        *, now: datetime | None = None,
    ) -> dict[str, Any]:
        value = float(amount)
        if not isfinite(value):
            raise ValueError("Сумма кредита должна быть конечным числом")
        value = round(value, 2)
        if value < MIN_BANK_LOAN or value > MAX_BANK_LOAN:
            raise ValueError(f"Сумма кредита — от {MIN_BANK_LOAN:,.0f} до {MAX_BANK_LOAN:,.0f} cash")
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        active_loan = await session.scalar(
            select(NatNextGameLoan).where(
                NatNextGameLoan.company_id == company.id,
                NatNextGameLoan.status == "ACTIVE",
            ).with_for_update()
        )
        if active_loan:
            raise ValueError("У компании уже есть активный кредит")
        treasury = await cls._treasury(session)
        if await cls._available_treasury_cash(session, treasury) + 1e-9 < value:
            raise ValueError("В банке 2.0 недостаточно свободных средств для такого кредита")
        current = now or _utcnow()
        company.cash = round(float(company.cash) + value, 2)
        treasury.cash = round(float(treasury.cash) - value, 2)
        loan = NatNextGameLoan(
            company_id=company.id, principal=value, status="ACTIVE",
            issued_at=current, due_at=current + timedelta(days=1),
        )
        session.add(loan)
        session.add(cls._ledger(
            company.id, "BANK_LOAN", value, -value,
            metadata={"principal": value, "daily_rate": BANK_LOAN_DAILY_RATE},
        ))
        await session.flush()
        return {"success": True, "company": cls.snapshot_company(company),
                "loan": cls._loan_snapshot(loan, current)}

    @classmethod
    async def repay_bank_loan(
        cls, session: AsyncSession, owner_tg_id: int, *, now: datetime | None = None,
    ) -> dict[str, Any]:
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        loan = await session.scalar(
            select(NatNextGameLoan).where(
                NatNextGameLoan.company_id == company.id,
                NatNextGameLoan.status == "ACTIVE",
            ).order_by(NatNextGameLoan.id.desc()).with_for_update()
        )
        if loan is None:
            raise ValueError("У компании нет активного кредита")
        current = now or _utcnow()
        days = max(1, min(MAX_BANK_LOAN_DAYS, ceil(max(0, (current - loan.issued_at).total_seconds()) / 86_400)))
        interest = round(float(loan.principal) * BANK_LOAN_DAILY_RATE * days, 2)
        total = round(float(loan.principal) + interest, 2)
        if float(company.cash) + 1e-9 < total:
            raise ValueError(f"Для погашения нужно {total:,.2f} cash с процентами за {days} дн.")
        treasury = await cls._treasury(session)
        company.cash = round(float(company.cash) - total, 2)
        treasury.cash = round(float(treasury.cash) + total, 2)
        loan.status = "PAID"
        loan.repaid_at = current
        session.add(cls._ledger(
            company.id, "BANK_REPAYMENT", -total, total,
            metadata={"principal": float(loan.principal), "interest": interest, "days": days},
        ))
        await session.flush()
        return {"success": True, "paid_amount": total, "interest": interest,
                "company": cls.snapshot_company(company)}

    @classmethod
    async def open_bank_deposit(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        amount: float,
        term_days: int,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        try:
            value = float(amount)
            raw_days = float(term_days)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Сумма и срок вклада должны быть числами") from exc
        if not isfinite(value):
            raise ValueError("Сумма вклада должна быть конечным числом")
        rounded_value = round(value, 2)
        if abs(value - rounded_value) > 1e-9:
            raise ValueError("Сумму вклада можно указать максимум с двумя знаками после запятой")
        value = rounded_value
        if value < MIN_BANK_DEPOSIT or value > MAX_BANK_DEPOSIT:
            raise ValueError(
                f"Сумма вклада — от {MIN_BANK_DEPOSIT:,.0f} до {MAX_BANK_DEPOSIT:,.0f} cash"
            )
        if not isfinite(raw_days) or not raw_days.is_integer():
            raise ValueError("Срок вклада должен быть целым числом дней")
        days = int(raw_days)
        if days < 1 or days > MAX_BANK_DEPOSIT_DAYS:
            raise ValueError(f"Срок вклада — от 1 до {MAX_BANK_DEPOSIT_DAYS} дней")

        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        if float(company.cash) + 1e-9 < value:
            raise ValueError("На балансе компании недостаточно cash для вклада")
        treasury = await cls._treasury(session)
        interest = round(value * BANK_DEPOSIT_DAILY_RATE * days, 2)
        maturity_amount = round(value + interest, 2)
        if await cls._available_treasury_cash(session, treasury) + 1e-9 < interest:
            raise ValueError("В казне 2.0 недостаточно свободного резерва для процентов по вкладу")
        current = now or _utcnow()
        deposit = NatNextGameDeposit(
            company_id=company.id,
            principal=value,
            maturity_amount=maturity_amount,
            term_days=days,
            daily_rate=BANK_DEPOSIT_DAILY_RATE,
            status="ACTIVE",
            opened_at=current,
            matures_at=current + timedelta(days=days),
        )
        company.cash = round(float(company.cash) - value, 2)
        treasury.cash = round(float(treasury.cash) + value, 2)
        session.add(deposit)
        await session.flush()
        session.add(cls._ledger(
            company.id, "BANK_DEPOSIT_OPEN", -value, value,
            metadata={"principal": value, "interest": interest, "term_days": days},
        ))
        await session.flush()
        return {
            "success": True,
            "deposit": cls._deposit_snapshot(deposit, current),
            "company": cls.snapshot_company(company),
        }

    @classmethod
    async def withdraw_bank_deposit(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        deposit_id: int,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        deposit = await session.scalar(
            select(NatNextGameDeposit).where(
                NatNextGameDeposit.id == int(deposit_id),
                NatNextGameDeposit.company_id == company.id,
            ).with_for_update()
        )
        if deposit is None or deposit.status != "ACTIVE":
            raise ValueError("Активный вклад не найден")
        current = now or _utcnow()
        if current < deposit.matures_at:
            raise ValueError("Срок вклада ещё не закончился")
        treasury = await cls._treasury(session)
        payout = round(float(deposit.maturity_amount), 2)
        if float(treasury.cash) + 1e-9 < payout:
            raise ValueError("В казне 2.0 пока недостаточно средств для выплаты вклада")
        interest = round(payout - float(deposit.principal), 2)
        company.cash = round(float(company.cash) + payout, 2)
        treasury.cash = round(float(treasury.cash) - payout, 2)
        deposit.status = "WITHDRAWN"
        deposit.withdrawn_at = current
        session.add(cls._ledger(
            company.id, "BANK_DEPOSIT_WITHDRAW", payout, -payout,
            metadata={
                "deposit_id": deposit.id,
                "principal": float(deposit.principal),
                "interest": interest,
            },
        ))
        await session.flush()
        return {
            "success": True,
            "interest": interest,
            "paid_amount": payout,
            "deposit": cls._deposit_snapshot(deposit, current),
            "company": cls.snapshot_company(company),
        }

    @staticmethod
    async def _deposit_liability(session: AsyncSession) -> float:
        value = await session.scalar(
            select(func.coalesce(func.sum(NatNextGameDeposit.maturity_amount), 0.0)).where(
                NatNextGameDeposit.status == "ACTIVE",
            )
        )
        return round(float(value or 0.0), 2)

    @staticmethod
    def _deposit_snapshot(deposit: NatNextGameDeposit, current: datetime) -> dict[str, Any]:
        principal = round(float(deposit.principal), 2)
        maturity_amount = round(float(deposit.maturity_amount), 2)
        return {
            "id": int(deposit.id),
            "status": str(deposit.status),
            "principal": principal,
            "interest": round(maturity_amount - principal, 2),
            "maturity_amount": maturity_amount,
            "daily_rate": float(deposit.daily_rate),
            "term_days": int(deposit.term_days),
            "opened_at": deposit.opened_at.isoformat(),
            "matures_at": deposit.matures_at.isoformat(),
            "withdrawn_at": deposit.withdrawn_at.isoformat() if deposit.withdrawn_at else None,
            "is_matured": current >= deposit.matures_at,
        }

    @staticmethod
    def _loan_snapshot(loan: NatNextGameLoan, current: datetime) -> dict[str, Any]:
        days = max(1, min(MAX_BANK_LOAN_DAYS, ceil(max(0, (current - loan.issued_at).total_seconds()) / 86_400)))
        interest = round(float(loan.principal) * BANK_LOAN_DAILY_RATE * days, 2)
        return {
            "id": loan.id, "status": loan.status,
            "principal": round(float(loan.principal), 2),
            "interest_due": interest,
            "repayment_amount": round(float(loan.principal) + interest, 2),
            "accrual_days": days,
            "issued_at": loan.issued_at.isoformat(),
            "due_at": loan.due_at.isoformat(),
        }
