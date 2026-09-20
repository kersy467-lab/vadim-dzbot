from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.reference_instrument_service import (
    ReferenceInstrumentService,
    StaleReferenceRate,
)

router = APIRouter(prefix="/instruments", tags=["Natbirzha Reference Instruments"])


class InstrumentTradeRequest(BaseModel):
    instrument_code: Literal["USD", "EUR", "GOLD", "SILVER"]
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0, le=1_000_000)


@router.get("")
async def get_reference_instruments(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return {
        "instruments": await ReferenceInstrumentService.catalog(session),
        "portfolio": await ReferenceInstrumentService.portfolio(session, company.id),
    }


@router.post("/trade")
async def trade_reference_instrument(
    req: InstrumentTradeRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")
    endpoint = "/api/natbirzha/instruments/trade"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        result = await ReferenceInstrumentService.trade(
            session,
            company.id,
            req.instrument_code,
            req.side,
            req.quantity,
            f"api:{company.id}:{idempotency_key}",
        )
    except StaleReferenceRate as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result
    )


__all__ = ["router"]
