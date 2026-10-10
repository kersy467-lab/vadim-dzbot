"""Facility actions for the isolated NATBIRZHA 2.0 mode."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.next_game_service import NextGameService

router = APIRouter(prefix="/facility", tags=["Natbirzha Next Game Facilities"])


class FacilityUpgradeRequest(BaseModel):
    branch_id: str = Field(min_length=2, max_length=64)


@router.post("/upgrade")
async def upgrade_facility(
    request: FacilityUpgradeRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    key = idempotency_key.strip()[:128]
    endpoint = "/api/natbirzha/next-game/facility/upgrade"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, key, payload)
    if cached:
        return cached[1]
    try:
        result = await NextGameService.upgrade_facility(
            session, int(admin.tg_id), request.branch_id,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )
