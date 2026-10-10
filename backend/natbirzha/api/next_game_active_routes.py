"""Administrator-only active-production sessions for the isolated 2.0 game."""

from typing import Awaitable, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.next_game_active_production_service import (
    NextGameActiveProductionService,
)

router = APIRouter(prefix="/next-game/active", tags=["Natbirzha Next Game Active Production"])


class StartRequest(BaseModel):
    branch_id: str = Field(min_length=2, max_length=64)


class SessionRequest(BaseModel):
    session_id: UUID
    session_token: str = Field(min_length=30, max_length=128)


class PulseRequest(SessionRequest):
    sequence: int = Field(ge=1)
    scene_action: Literal["idle", "move", "pickup", "deliver", "interact", "tap"]
    user_input_counter: int = Field(ge=0, le=2_147_483_647)


async def _commit(session: AsyncSession, action: Awaitable[dict]) -> dict:
    try:
        result = await action
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise


@router.get("/config")
async def get_config(
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _commit(session, NextGameActiveProductionService.config(session, int(admin.tg_id)))


@router.get("/status")
async def get_status(
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _commit(session, NextGameActiveProductionService.status(session, int(admin.tg_id)))


@router.post("/start")
async def start_session(
    request: StartRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _commit(session, NextGameActiveProductionService.start(
        session, int(admin.tg_id), request.branch_id,
    ))


@router.post("/pulse")
async def pulse_session(
    request: PulseRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _commit(session, NextGameActiveProductionService.pulse(
        session, int(admin.tg_id), str(request.session_id), request.session_token,
        request.sequence, request.scene_action, request.user_input_counter,
    ))


@router.post("/pause")
async def pause_session(
    request: SessionRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _commit(session, NextGameActiveProductionService.finish(
        session, int(admin.tg_id), str(request.session_id), request.session_token,
        status="PAUSED", reason="user_pause",
    ))


@router.post("/stop")
async def stop_session(
    request: SessionRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _commit(session, NextGameActiveProductionService.finish(
        session, int(admin.tg_id), str(request.session_id), request.session_token,
        status="STOPPED", reason="user_exit",
    ))


__all__ = ["router"]
