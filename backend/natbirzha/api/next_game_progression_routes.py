"""Idempotent upgrades, source-consuming fusion and confirmed rebirth."""
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.services.next_game_progression_service import NextGameProgressionService as Progression
from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService as Fusion

router = APIRouter(prefix="/next-game/progression", tags=["Next Game Progression"])


class RebirthRequest(BaseModel):
    confirm: bool = False


class FusionRequest(BaseModel):
    source_ids: list[int] = Field(min_length=2, max_length=2)


class DissolveRequest(BaseModel):
    merger_id: int = Field(gt=0)


@router.get("")
async def snapshot(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    await Progression.sweep_reserve_income(session)
    result = await Progression.snapshot(session, int(admin.tg_id))
    await session.commit()
    return result


@router.post("/pvc-upgrade")
async def pvc_upgrade(key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/next-game/progression/pvc-upgrade", {},
        lambda: Progression.upgrade_pvc(session, int(admin.tg_id)))


@router.post("/rebirth")
async def rebirth(body: RebirthRequest, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/next-game/progression/rebirth", body.model_dump(),
        lambda: Progression.rebirth(session, int(admin.tg_id), confirm=body.confirm))


@router.post("/fuse")
async def fuse(body: FusionRequest, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/next-game/progression/fuse", body.model_dump(),
        lambda: Fusion.fuse(session, int(admin.tg_id), body.source_ids))


@router.post("/dissolve")
async def dissolve(body: DissolveRequest, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/next-game/progression/dissolve", body.model_dump(),
        lambda: Fusion.dissolve(session, int(admin.tg_id), body.merger_id))
