"""API endpoints for checking and toggling Natbirzha maintenance mode."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.services.access_control import get_creator_tg_ids, is_creator_user
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.services.maintenance_service import MaintenanceService

router = APIRouter(tags=["Natbirzha Maintenance"])


def _is_admin(user: User) -> bool:
    return bool(
        is_creator_user(user)
        or (user.tg_id and user.tg_id in get_creator_tg_ids())
        or user.role == "admin"
    )


class MaintenanceSetRequest(BaseModel):
    enabled: bool


@router.get("/maintenance")
async def get_maintenance_status(
    session: AsyncSession = Depends(get_db_session),
):
    """Return whether Natbirzha maintenance mode is currently active."""
    active = await MaintenanceService.is_maintenance_active(session)
    return {"maintenance_mode": active}


@router.post("/creator/maintenance/toggle")
async def toggle_maintenance_mode(
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Toggle maintenance mode on or off. Creator or Admin only."""
    if not _is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён: требуются полномочия Администратора государства.",
        )
    new_state = await MaintenanceService.toggle_maintenance(session)
    return {"maintenance_mode": new_state}


@router.post("/creator/maintenance/set")
async def set_maintenance_mode(
    payload: MaintenanceSetRequest,
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Explicitly set maintenance mode on or off. Creator or Admin only."""
    if not _is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён: требуются полномочия Администратора государства.",
        )
    result = await MaintenanceService.set_maintenance_active(session, payload.enabled)
    return {"maintenance_mode": result}
