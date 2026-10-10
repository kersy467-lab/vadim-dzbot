"""Administrator-only bilateral finance contracts in NATBIRZHA 2.0."""

from math import isfinite

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.next_game_finance_service import (
    MAX_DAILY_RATE_BPS,
    MAX_PRINCIPAL,
    MIN_PRINCIPAL,
    NextGameFinanceContractService,
)


router = APIRouter(prefix="/next-game/finance", tags=["Natbirzha Next Game Finance"])


class DirectLoanOfferRequest(BaseModel):
    borrower_company_id: int = Field(ge=1)
    principal: float = Field(ge=MIN_PRINCIPAL, le=MAX_PRINCIPAL)
    daily_rate_bps: int = Field(ge=0, le=MAX_DAILY_RATE_BPS)
    term_days: int = Field(ge=1, le=30)

    @field_validator("principal")
    @classmethod
    def validate_principal(cls, value: float) -> float:
        if not isfinite(value) or abs(value - round(value, 2)) > 1e-9:
            raise ValueError("Сумму займа можно указать максимум с двумя знаками")
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


@router.post("/offers")
async def create_offer(
    request: DirectLoanOfferRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_key(idempotency_key)
    payload = request.model_dump()
    return await _run_idempotent(
        session, admin, "/api/natbirzha/next-game/finance/offers", key, payload,
        lambda: NextGameFinanceContractService.create_offer(
            session, int(admin.tg_id), request.borrower_company_id,
            request.principal, request.daily_rate_bps, request.term_days,
            idempotency_key=key,
        ),
    )


@router.post("/offers/{contract_id}/accept")
async def accept_offer(
    contract_id: int,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_key(idempotency_key)
    return await _run_idempotent(
        session, admin, "/api/natbirzha/next-game/finance/offers/accept", key,
        {"contract_id": int(contract_id)},
        lambda: NextGameFinanceContractService.accept_offer(
            session, int(admin.tg_id), int(contract_id), idempotency_key=key,
        ),
    )


@router.post("/offers/{contract_id}/cancel")
async def cancel_offer(
    contract_id: int,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_key(idempotency_key)
    return await _run_idempotent(
        session, admin, "/api/natbirzha/next-game/finance/offers/cancel", key,
        {"contract_id": int(contract_id)},
        lambda: NextGameFinanceContractService.cancel_offer(
            session, int(admin.tg_id), int(contract_id), idempotency_key=key,
        ),
    )


@router.post("/loans/{contract_id}/repay")
async def repay_loan(
    contract_id: int,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_key(idempotency_key)
    return await _run_idempotent(
        session, admin, "/api/natbirzha/next-game/finance/loans/repay", key,
        {"contract_id": int(contract_id)},
        lambda: NextGameFinanceContractService.repay_loan(
            session, int(admin.tg_id), int(contract_id), idempotency_key=key,
        ),
    )


__all__ = ["router"]
