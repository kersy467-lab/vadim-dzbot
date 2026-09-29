"""Creator-only reset routes for company self-reset, season reset and world reset."""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.season_reset_service import SeasonResetService
from backend.natbirzha.services.world_reset_service import WorldResetService
from backend.natbirzha.api.creator_auth import get_current_creator

router = APIRouter(tags=["Natbirzha Creator Reset"])


class SeasonResetRequest(BaseModel):
    operation_id: str = Field(min_length=1, max_length=120)
    backup_reference: str = Field(min_length=1, max_length=255)


class WorldResetRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=64)


@router.post("/me/reset")
async def reset_self(
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete only the creator's own company. User record and admin role are preserved.
    Next company creation uses the normal cash balance plus the creator's PVC grant."""
    comp_res = await session.execute(
        select(NatCompany).where(NatCompany.user_id == admin.id)
    )
    company = comp_res.scalar_one_or_none()
    if not company:
        return {"ok": True, "message": "Компании нет — уже чисто.", "deleted_company": None}

    company_name = company.name
    company_id = company.id
    try:
        await CompanyService.reset_company_for_user(session, admin.id, commit=True)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сброса: {exc}") from exc

    starting_cash_text = f"{nat_settings.STARTING_CASH:,.0f}".replace(",", " ")
    return {
        "ok": True,
        "message": f"Компания «{company_name}» удалена. При новом создании стартовый баланс: {starting_cash_text} cash + 200 PVC.",
        "deleted_company": company_name,
        "deleted_company_id": company_id,
    }


@router.get("/season-reset/preview")
async def season_reset_preview(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return await SeasonResetService.preview(session)


@router.post("/season-reset")
async def season_reset(
    req: SeasonResetRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    if not nat_settings.SEASON_RESET_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Season reset is disabled. Create a verified backup and set NATBIRZHA_SEASON_RESET_ENABLED=true for one operation.",
        )
    try:
        return await SeasonResetService.execute(
            session,
            operation_id=req.operation_id,
            actor_tg_id=admin.tg_id,
            backup_reference=req.backup_reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/world-reset/preview")
async def world_reset_preview(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return await WorldResetService.preview(session)


@router.post("/world-reset")
async def world_reset(
    req: WorldResetRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await WorldResetService.execute(
            session, actor_tg_id=admin.tg_id, confirmation=req.confirmation
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


__all__ = [
    "router",
    "SeasonResetRequest",
    "WorldResetRequest",
    "reset_self",
    "season_reset_preview",
    "season_reset",
    "world_reset_preview",
    "world_reset",
]
