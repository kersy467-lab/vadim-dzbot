from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.npc_service import NPCReserveService

router = APIRouter(prefix="/market", tags=["Natbirzha Market"])


class CreateOrderRequest(BaseModel):
    order_type: Optional[str] = None
    side: Optional[str] = None
    item_id: str
    price: float = Field(gt=0)
    quantity: Optional[float] = None
    amount: Optional[float] = None


class NPCTradeRequest(BaseModel):
    item_id: str
    action: Optional[str] = None
    operation: Optional[str] = None
    quantity: float = Field(gt=0)


class CancelOrderRequest(BaseModel):
    order_id: int


@router.get("/orderbook")
async def get_orderbook(
    item_id: str = Query(..., description="Item canonical ID"),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await MarketService.get_orderbook(session, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/create")
@router.post("/order/place")
async def create_order(
    req: CreateOrderRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = "/api/natbirzha/market/orders/create"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]

    try:
        order_type = (req.order_type or req.side or "BUY").upper()
        quantity = req.quantity if req.quantity is not None else (req.amount or 1.0)
        order = await MarketService.create_order(
            session, company, order_type, req.item_id, req.price, quantity, commit=False
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = {
        "success": True,
        "order_id": order.id,
        "order_type": order.order_type,
        "item_id": order.item_id,
        "price": order.price,
        "quantity": order.quantity,
        "remaining_qty": order.remaining_qty,
        "status": order.status,
    }
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = f"/api/natbirzha/market/orders/{order_id}/cancel"
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, {}
    )
    if cached:
        return cached[1]

    success = await MarketService.cancel_order(session, company, order_id, commit=False)
    if not success:
        raise HTTPException(status_code=404, detail="Active order not found or not owned by company.")
    response = {"success": True, "cancelled_order_id": order_id}
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, {}, response
    )


@router.post("/order/cancel")
async def cancel_order_body(
    req: CancelOrderRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return await cancel_order(req.order_id, idempotency_key, company, session)


@router.get("/npc/rates")
async def get_npc_rates(session: AsyncSession = Depends(get_db_session)):
    quota = await NPCReserveService.get_daily_quota(session)
    rates = []
    for item_id in CANONICAL_ITEMS:
        buy_status = await NPCReserveService.get_quota_status(session, item_id, "BUY")
        sell_status = await NPCReserveService.get_quota_status(session, item_id, "SELL")
        rates.append({
            **NPCReserveService.get_npc_quote(item_id),
            # Regular-resource NPC liquidity is unlimited in both directions.
            # Keep the old response keys as null for backward compatibility.
            "scaling_factor": 1.0,
            "liquidity_unlimited": True,
            "daily_quota": None,
            "remaining_npc_quota": None,
            "quota_label": "",
            "player_sell_daily_quota": None,
            "player_sell_remaining_quota": None,
            # Premium raw materials have a separate emergency stock only when
            # the player buys them from NPC. This is not general liquidity.
            "strict_reserve": bool(buy_status["strict_reserve"]),
            "rare_npc_buy_daily_quota": buy_status["daily_quota"],
            "rare_npc_buy_remaining": buy_status["remaining_npc_quota"],
            "rare_npc_buy_label": buy_status["quota_label"],
        })
    return {"rates": rates, **quota}


@router.post("/npc/trade")
async def trade_with_npc(
    req: NPCTradeRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = "/api/natbirzha/market/npc/trade"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]

    action = (req.action or req.operation or "BUY").upper()
    result = await NPCReserveService.execute_npc_trade(
        session, company, req.item_id, action, req.quantity
    )
    if not result.get("success"):
        reason = result.get("reason")
        code = 409 if reason in {"npc_rare_reserve_empty", "market_restricted", "inventory_overflow"} else 400
        raise HTTPException(status_code=code, detail=result)

    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result
    )


__all__ = ["router"]
