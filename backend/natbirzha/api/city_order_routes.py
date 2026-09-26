"""Authenticated listing and delivery endpoints for city-funded resource orders."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.city_order_service import CityOrderService
from backend.natbirzha.services.idempotency_service import IdempotencyService


router = APIRouter(prefix="/market/city-orders", tags=["Natbirzha City Orders"])


class CityOrderDeliveryRequest(BaseModel):
    quantity: float = Field(gt=0, le=1_000_000_000)


@router.get("")
async def list_city_orders(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    # Reads also close any deadline reached since the minute scheduler last ran.
    if await CityOrderService.expire_due(session):
        await session.commit()
    return {"orders": await CityOrderService.list_orders(session)}


@router.post("/{order_id}/deliver")
async def deliver_city_order(
    order_id: int,
    req: CityOrderDeliveryRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    # Include the current company ID so an old key cannot replay after a reset
    # when the same user has a new company and retries this shared order.
    endpoint = f"/api/natbirzha/market/city-orders/{order_id}/deliver/company/{company.id}"
    payload = {"order_id": order_id, "quantity": req.quantity}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    try:
        response = await CityOrderService.deliver(
            session, company.id, order_id, req.quantity,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        message = str(exc)
        status = 409 if any(
            token in message.lower()
            for token in ("закрыт", "истёк", "превышает", "недостаточно", "идемпотентности")
        ) else 400
        raise HTTPException(status_code=status, detail=message) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


__all__ = ["router"]
