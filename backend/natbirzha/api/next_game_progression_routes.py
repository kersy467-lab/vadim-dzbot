"""Persistent progression upgrades, managers and source-consuming factory fusion."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.services.next_game_progression_service import NextGameProgressionService as Progression
from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService as Fusion
from backend.natbirzha.services.next_game_manager_service import assign_manager

router = APIRouter(prefix="/next-game/progression", tags=["Next Game Progression"])


class FusionRequest(BaseModel):
    source_ids: list[int] = Field(min_length=2, max_length=2)


class DissolveRequest(BaseModel):
    merger_id: int = Field(gt=0)


class ManagerAssignmentRequest(BaseModel):
    manager_id: int = Field(gt=0)
    branch_id: str | None = Field(default=None, min_length=2, max_length=64)


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
async def rebirth_disabled(admin: User = Depends(get_current_creator)):
    raise HTTPException(
        status_code=410,
        detail="Перерождения отключены: развитие компании и заводов сохраняется без сброса.",
    )


@router.post("/manager/assign")
async def manager_assign(
    body: ManagerAssignmentRequest,
    key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    payload = body.model_dump()
    return await mutate(
        session, admin, key, "/next-game/progression/manager/assign", payload,
        lambda: assign_manager(
            session, int(admin.tg_id), body.manager_id, body.branch_id,
        ),
    )


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
