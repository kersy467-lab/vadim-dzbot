"""Creator approval endpoints for Treasury-backed state credit."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_routes import get_current_creator
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.state_credit_service import StateCreditService


router = APIRouter(prefix="/creator/state-credits", tags=["Natbirzha Creator State Credit"])


class StateCreditDecisionRequest(BaseModel):
    approved: bool
    reason: Optional[str] = Field(default=None, max_length=255)


def _require_idempotency_key(key: Optional[str]) -> str:
    if not key or not key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")
    if len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long.")
    return key.strip()


@router.get("")
async def get_creator_state_credit_requests(
    status: str = Query(default="PENDING", pattern="^(PENDING|ALL)$"),
    _creator: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return await StateCreditService.creator_requests(session, status)


@router.post("/{loan_id}/decision")
async def decide_creator_state_credit(
    loan_id: int,
    request: StateCreditDecisionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    creator: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    key = _require_idempotency_key(idempotency_key)
    endpoint = f"/api/natbirzha/creator/state-credits/{loan_id}/decision"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, creator.id, endpoint, key, payload
    )
    if cached:
        return cached[1]
    try:
        result = await StateCreditService.decide(
            session,
            loan_id,
            actor_id=creator.tg_id,
            approved=request.approved,
            commit=False,
        )
        return await IdempotencyService.commit_response(
            session, creator.id, endpoint, key, payload, result
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


__all__ = ["router"]
