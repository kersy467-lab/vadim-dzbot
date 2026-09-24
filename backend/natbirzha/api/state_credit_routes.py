"""Player endpoints for Treasury-backed fixed-interest state credit."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.state_credit_service import StateCreditService


router = APIRouter(prefix="/finance/state-loans", tags=["Natbirzha State Credit"])


class StateCreditRequest(BaseModel):
    principal: float = Field(gt=0)
    term_days: int = Field(ge=1, le=5)


class StateCreditRepaymentRequest(BaseModel):
    amount: float = Field(gt=0)


def _require_idempotency_key(key: Optional[str]) -> str:
    if not key or not key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")
    if len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long.")
    return key.strip()


async def _replay_after_competing_mutation(
    session: AsyncSession,
    user_id: int,
    endpoint: str,
    key: str,
    payload: dict,
) -> dict | None:
    """Recheck a same-key winner after a lock made this request observe its result."""
    await session.rollback()
    cached = await IdempotencyService.check_or_conflict(
        session, user_id, endpoint, key, payload
    )
    return cached[1] if cached else None


@router.get("")
async def get_state_credit_status(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return await StateCreditService.status(session, company)


@router.post("")
async def request_state_credit(
    request: StateCreditRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/finance/state-loans"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, key, payload
    )
    if cached:
        return cached[1]
    try:
        response = await StateCreditService.request(
            session,
            company,
            request.principal,
            request.term_days,
            commit=False,
        )
    except ValueError as exc:
        cached = await _replay_after_competing_mutation(
            session, company.user_id, endpoint, key, payload
        )
        if cached:
            return cached
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, key, payload, response
    )


@router.post("/{loan_id}/repay")
async def repay_state_credit(
    loan_id: int,
    request: StateCreditRepaymentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    key = _require_idempotency_key(idempotency_key)
    endpoint = f"/api/natbirzha/finance/state-loans/{loan_id}/repay"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, key, payload
    )
    if cached:
        return cached[1]
    try:
        response = await StateCreditService.repay(
            session, company, loan_id, request.amount, commit=False
        )
    except ValueError as exc:
        cached = await _replay_after_competing_mutation(
            session, company.user_id, endpoint, key, payload
        )
        if cached:
            return cached
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, key, payload, response
    )


__all__ = ["router"]
