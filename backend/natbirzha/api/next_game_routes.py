"""Server-gated administrator routes for the next-game sandbox."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.next_game_service import NextGameService

router = APIRouter(prefix="/next-game", tags=["Natbirzha Next Game Preview"])


class CreateSandboxCompany(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class SelectSector(BaseModel):
    sector_id: str = Field(min_length=2, max_length=48)


class SelectBranch(BaseModel):
    branch_id: str = Field(min_length=2, max_length=64)


@router.get("/map")
async def get_map(
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await NextGameService.snapshot(session, int(admin.tg_id))


@router.post("/company")
async def create_company(
    request: CreateSandboxCompany,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        result = await NextGameService.create_company(session, int(admin.tg_id), request.name)
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/sector")
async def select_sector(
    request: SelectSector,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        result = await NextGameService.select_sector(
            session, int(admin.tg_id), request.sector_id
        )
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/branch")
async def select_branch(
    request: SelectBranch,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        result = await NextGameService.select_branch(
            session, int(admin.tg_id), request.branch_id
        )
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = ["router"]
