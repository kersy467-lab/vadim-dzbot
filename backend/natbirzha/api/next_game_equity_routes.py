"""Administrator-only IPO and dividend actions for the isolated 2.0 mode."""

from math import isfinite
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.next_game_equity_service import NextGameEquityService

router = APIRouter(prefix="/next-game/capital", tags=["Natbirzha Next Game Capital"])


class ShareOrderRequest(BaseModel):
    issue_id: int = Field(ge=1)
    side: Literal["BUY", "SELL"]
    shares: int = Field(ge=1, le=1_000_000)
    limit_price: float = Field(gt=0, le=1_000_000_000)

    @field_validator("limit_price")
    @classmethod
    def validate_price(cls, value: float) -> float:
        if not isfinite(value) or abs(value - round(value, 4)) > 1e-9:
            raise ValueError("Цена должна быть конечной, максимум с четырьмя знаками")
        return value


class DividendRequest(BaseModel):
    per_share: float = Field(ge=0.01, le=1_000_000)

    @field_validator("per_share")
    @classmethod
    def validate_dividend(cls, value: float) -> float:
        if not isfinite(value) or abs(value - round(value, 4)) > 1e-9:
            raise ValueError("Дивиденд должен быть конечным числом с точностью до 4 знаков")
        return value


def _key(value: str | None) -> str:
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    return value.strip()[:128]


async def _commit_action(session, admin, endpoint, key, payload, action):
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


@router.post("/ipo")
async def open_ipo(
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/capital/ipo"
    return await _commit_action(
        session, admin, endpoint, key, {},
        lambda: NextGameEquityService.open_ipo(session, int(admin.tg_id)),
    )


@router.post("/orders")
async def create_share_order(
    request: ShareOrderRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/capital/orders"
    payload = request.model_dump()
    return await _commit_action(
        session, admin, endpoint, key, payload,
        lambda: NextGameEquityService.create_order(
            session, int(admin.tg_id), request.issue_id, request.side,
            request.shares, request.limit_price,
        ),
    )


@router.delete("/orders/{order_id}")
async def cancel_share_order(
    order_id: int,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _key(idempotency_key)
    endpoint = f"/api/natbirzha/next-game/capital/orders/{order_id}"
    return await _commit_action(
        session, admin, endpoint, key, {"order_id": order_id},
        lambda: NextGameEquityService.cancel_order(session, int(admin.tg_id), order_id),
    )


@router.post("/dividends")
async def distribute_dividend(
    request: DividendRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/capital/dividends"
    payload = request.model_dump()
    return await _commit_action(
        session, admin, endpoint, key, payload,
        lambda: NextGameEquityService.distribute_dividend(
            session, int(admin.tg_id), request.per_share,
        ),
    )


__all__ = ["router"]
