from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.loan_service import LoanService

router = APIRouter(prefix="/finance", tags=["Natbirzha Finance"])


class BorrowRequest(BaseModel):
    principal: float = Field(gt=0)


class RepayRequest(BaseModel):
    amount: float = Field(gt=0)


@router.get("/loans")
async def get_loans(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return await LoanService.status(session, company)


@router.post("/loans")
async def borrow(
    req: BorrowRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = "/api/natbirzha/finance/loans"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        response = await LoanService.borrow(session, company, req.principal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


@router.post("/loans/{loan_id}/repay")
async def repay(
    loan_id: int,
    req: RepayRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = f"/api/natbirzha/finance/loans/{loan_id}/repay"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        response = await LoanService.repay(session, company, loan_id, req.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


__all__ = ["router"]
