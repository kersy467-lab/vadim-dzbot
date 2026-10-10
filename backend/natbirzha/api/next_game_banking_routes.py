"""Admin-only corporate account and settlement actions for the 2.0 sandbox."""

from math import isfinite

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.next_game_banking_service import (
    MAX_BUSINESS_LOAN,
    MAX_PAYMENT,
    MIN_PAYMENT,
    NextGameBankingService,
)

router = APIRouter(prefix="/next-game/banking", tags=["Natbirzha Next Game Banking"])


class OpenAccountRequest(BaseModel):
    bank_company_id: int = Field(ge=1)


class TransferRequest(BaseModel):
    bank_company_id: int = Field(ge=1)
    payee_company_id: int = Field(ge=1)
    amount: float = Field(ge=MIN_PAYMENT, le=MAX_PAYMENT)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        if not isfinite(value) or abs(value - round(value, 2)) > 1e-9:
            raise ValueError("Сумму платежа можно указать максимум с двумя знаками")
        return round(value, 2)


class BusinessLoanRequest(BaseModel):
    bank_company_id: int = Field(ge=1)
    amount: float = Field(ge=1_000, le=MAX_BUSINESS_LOAN)
    term_days: int = Field(ge=1, le=30)

    @field_validator("amount")
    @classmethod
    def validate_loan_amount(cls, value: float) -> float:
        if not isfinite(value) or abs(value - round(value, 2)) > 1e-9:
            raise ValueError("Сумму кредита можно указать максимум с двумя знаками")
        return round(value, 2)


def _require_key(value: str | None) -> str:
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    return value.strip()[:128]


async def _run_idempotent(session, admin, endpoint, key, payload, action):
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        result = await action()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.post("/accounts")
async def open_account(
    request: OpenAccountRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _run_idempotent(
        session, admin, "/api/natbirzha/next-game/banking/accounts",
        _require_key(idempotency_key), request.model_dump(),
        lambda: NextGameBankingService.open_account(
            session, int(admin.tg_id), request.bank_company_id,
        ),
    )


@router.post("/payments")
async def make_payment(
    request: TransferRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _run_idempotent(
        session, admin, "/api/natbirzha/next-game/banking/payments",
        _require_key(idempotency_key), request.model_dump(),
        lambda: NextGameBankingService.transfer(
            session, int(admin.tg_id), request.bank_company_id,
            request.payee_company_id, request.amount,
            idempotency_key=_require_key(idempotency_key),
        ),
    )


@router.post("/loans")
async def request_business_loan(
    request: BusinessLoanRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_key(idempotency_key)
    payload = request.model_dump()
    return await _run_idempotent(
        session, admin, "/api/natbirzha/next-game/banking/loans", key, payload,
        lambda: NextGameBankingService.request_business_loan(
            session, int(admin.tg_id), request.bank_company_id,
            request.amount, request.term_days, idempotency_key=key,
        ),
    )


@router.post("/loans/{loan_id}/repay")
async def repay_business_loan(
    loan_id: int,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_key(idempotency_key)
    payload = {"loan_id": int(loan_id)}
    return await _run_idempotent(
        session, admin, "/api/natbirzha/next-game/banking/loans/repay", key, payload,
        lambda: NextGameBankingService.repay_business_loan(
            session, int(admin.tg_id), int(loan_id), idempotency_key=key,
        ),
    )


__all__ = ["router"]
