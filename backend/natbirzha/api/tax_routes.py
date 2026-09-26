"""Mandatory 12-hour net-profit tax endpoints shown inside the market screen."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.tax_service import TaxService


router = APIRouter(prefix="/tax", tags=["Natbirzha Tax"])


class TaxPaymentRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0)


@router.get("")
async def get_tax_status(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    settlement = await IdleEconomyService.settle_company(session, company.id)
    summary = settlement.get("tax") or await TaxService.summary(session, company.id)
    await session.commit()
    return summary


@router.post("/pay")
async def pay_tax(
    request: TaxPaymentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    endpoint = "/api/natbirzha/tax/pay"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        await IdleEconomyService.settle_company(session, company.id)
        response = await TaxService.pay(session, company.id, request.amount)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


__all__ = ["router"]
