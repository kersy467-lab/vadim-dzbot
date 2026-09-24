"""Player access to confiscated enterprise lots."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.bankruptcy_market_service import BankruptcyMarketService
from backend.natbirzha.services.idempotency_service import IdempotencyService


router = APIRouter(prefix="/bankruptcy-market", tags=["Natbirzha Bankruptcy Market"])


@router.get("")
async def get_bankruptcy_lots(session: AsyncSession = Depends(get_db_session)):
    return {"lots": await BankruptcyMarketService.get_active_lots(session)}


@router.post("/lots/{lot_id}/buy")
async def buy_bankruptcy_lot(
    lot_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = f"/api/natbirzha/bankruptcy-market/lots/{lot_id}/buy"
    payload = {"lot_id": lot_id}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload,
    )
    if cached:
        return cached[1]
    try:
        result = await BankruptcyMarketService.purchase_lot(
            session, company_id=company.id, lot_id=lot_id, commit=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.get("success"):
        # Keep stale-lot cleanup durable while still returning a conflict to the
        # buyer; raising before this commit would roll the cancellation back.
        await session.commit()
        raise HTTPException(status_code=409, detail=result.get("message", "Лот больше недоступен."))
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result,
    )


__all__ = ["router"]
