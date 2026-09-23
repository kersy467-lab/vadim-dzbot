"""Creator controls and player endpoints for fixed-price state shares."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_routes import get_current_creator
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.state_share_service import (
    StateShareIdempotencyConflict,
    StateShareService,
)


creator_router = APIRouter(prefix="/creator/shares", tags=["Natbirzha State Shares Creator"])
player_router = APIRouter(prefix="/shares", tags=["Natbirzha State Shares"])


class IssueStateShareRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    purpose: str = Field(default="", max_length=255)
    volume: int = Field(gt=0, le=2_000_000_000)
    issue_price: float = Field(gt=0, le=1_000_000_000_000)
    projected_annual_profit: float = Field(ge=0, le=1_000_000_000_000_000)
    dividend_rate_pct: float = Field(ge=0, le=100)


class StateShareTradeRequest(BaseModel):
    quantity: int = Field(gt=0, le=2_000_000_000)


def _require_idempotency_key(key: Optional[str]) -> str:
    if not key or not key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")
    if len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long.")
    return key.strip()


async def _recover_idempotency_race(
    session: AsyncSession,
    user_id: int,
    endpoint: str,
    key: str,
    payload: dict,
) -> dict:
    """Roll back the losing transaction and replay its committed winner."""
    await session.rollback()
    cached = await IdempotencyService.check_or_conflict(
        session, user_id, endpoint, key, payload
    )
    if cached:
        return cached[1]
    raise HTTPException(
        status_code=409,
        detail="A concurrent state share request conflicted; retry with the same key.",
    )


@creator_router.post("/issue")
async def issue_state_shares(
    request: IssueStateShareRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    creator: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/creator/shares/issue"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, creator.id, endpoint, key, payload)
    if cached:
        return cached[1]
    try:
        result = await StateShareService.issue(
            session,
            actor_id=creator.tg_id,
            title=request.title,
            purpose=request.purpose,
            volume=request.volume,
            issue_price=request.issue_price,
            projected_annual_profit=request.projected_annual_profit,
            dividend_rate_pct=request.dividend_rate_pct,
            operation_key=f"api:state-share:issue:{creator.id}:{key}",
            commit=False,
        )
        return await IdempotencyService.commit_response(
            session, creator.id, endpoint, key, payload, result
        )
    except StateShareIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError:
        return await _recover_idempotency_race(
            session, creator.id, endpoint, key, payload
        )


@creator_router.get("")
async def list_state_shares_for_creator(
    _creator: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return {"shares": await StateShareService.list_shares(session)}


@player_router.get("")
async def list_state_shares_for_player(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    shares = await StateShareService.list_shares(session, company_id=company.id)
    return {"shares": [row for row in shares if row["is_active"]]}


@player_router.post("/{share_id}/buy")
async def buy_state_shares(
    share_id: int,
    request: StateShareTradeRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    key = _require_idempotency_key(idempotency_key)
    endpoint = f"/api/natbirzha/shares/{share_id}/buy"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, key, payload)
    if cached:
        return cached[1]
    try:
        result = await StateShareService.buy(
            session,
            company,
            share_id,
            request.quantity,
            operation_key=f"api:state-share:buy:{company.id}:{share_id}:{key}",
            commit=False,
        )
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, key, payload, result
        )
    except StateShareIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError:
        return await _recover_idempotency_race(
            session, company.user_id, endpoint, key, payload
        )


@player_router.post("/{share_id}/sell")
async def sell_state_shares(
    share_id: int,
    request: StateShareTradeRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    key = _require_idempotency_key(idempotency_key)
    endpoint = f"/api/natbirzha/shares/{share_id}/sell"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, key, payload)
    if cached:
        return cached[1]
    try:
        result = await StateShareService.sell(
            session,
            company,
            share_id,
            request.quantity,
            operation_key=f"api:state-share:sell:{company.id}:{share_id}:{key}",
            commit=False,
        )
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, key, payload, result
        )
    except StateShareIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError:
        return await _recover_idempotency_race(
            session, company.user_id, endpoint, key, payload
        )


__all__ = ["creator_router", "player_router"]
