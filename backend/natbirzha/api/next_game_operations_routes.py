"""Authenticated, idempotent civilian operating asset commands."""
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_operations_service import NextGameOperationsService as Service
from backend.natbirzha.services.next_game_operations_read import snapshot

router = APIRouter(prefix="/next-game/operations", tags=["Next Game Operations"])


class Operation(BaseModel):
    action: Literal["LAND", "WAREHOUSE", "AUTOMATION", "LICENSE", "HIRE", "FIRE", "VEHICLE", "REPAIR", "SCRAP"]
    facility_id: int | None = Field(default=None, gt=0)
    asset_id: int | None = Field(default=None, gt=0)
    kind: str | None = Field(default=None, max_length=48)


@router.get("")
async def read(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    try:
        await Game.settle_company(session, int(admin.tg_id))
        result = await snapshot(session, int(admin.tg_id))
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/actions")
async def action(body: Operation, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/next-game/operations/actions", body.model_dump(),
        lambda: Service.operate(session, int(admin.tg_id), **body.model_dump()))
