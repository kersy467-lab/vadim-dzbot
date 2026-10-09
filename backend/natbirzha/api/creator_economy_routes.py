"""Creator controls for Treasury policy and foreign resource exports."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.state_economy_service import StateEconomyService


router = APIRouter(tags=["Natbirzha Creator State Economy"])


class ForeignExportsRequest(BaseModel):
    enabled: bool


@router.get("/economy/state")
async def get_state_economy(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return await StateEconomyService.creator_snapshot(session)


@router.post("/economy/foreign-exports")
async def set_state_foreign_exports(
    request: ForeignExportsRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return await StateEconomyService.set_foreign_exports_enabled(
        session, enabled=request.enabled, actor_id=admin.tg_id
    )


__all__ = ["router", "ForeignExportsRequest", "get_state_economy", "set_state_foreign_exports"]
