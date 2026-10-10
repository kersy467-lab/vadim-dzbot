"""Authorized aid, settings and sandbox administration endpoints."""
from typing import Literal
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.services.next_game_admin_service import NextGameAdminService
from backend.natbirzha.services.next_game_community_service import NextGameCommunityService, profile
from backend.natbirzha.services.next_game_service import NextGameService

router = APIRouter(prefix="/next-game", tags=["Next Game Community"])


class AidRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    item_id: str | None = Field(default=None, max_length=64)
    goal: float = Field(gt=0, le=1_000_000_000)
    description: str = Field(default="", max_length=240)


class Donation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    quantity: float = Field(gt=0, le=1_000_000_000)


class Settings(BaseModel):
    auto_upgrade: bool


class AdminOperation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    action: Literal["TREASURY_TOPUP", "CASH_GRANT", "ITEM_GRANT", "PVC_GRANT"]
    company_id: int | None = None
    value: float = Field(gt=0, le=100_000_000_000_000)
    item_id: str | None = Field(default=None, max_length=64)
    note: str = Field(min_length=1, max_length=240)


@router.get("/support")
async def support(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await NextGameCommunityService.snapshot(session, int(admin.tg_id))


@router.post("/support/requests")
async def request_help(body: AidRequest, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/next-game/support/requests", body.model_dump(),
        lambda: NextGameCommunityService.create_request(session, int(admin.tg_id), body.item_id, body.goal, body.description))


@router.post("/support/requests/{request_id}/donate")
async def donate(request_id: int, body: Donation, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    payload = {"request_id": request_id, **body.model_dump()}
    return await mutate(session, admin, key, "/next-game/support/donate", payload,
        lambda: NextGameCommunityService.donate(session, int(admin.tg_id), request_id, body.quantity))


@router.delete("/support/requests/{request_id}")
async def close_request(request_id: int, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/next-game/support/close", {"request_id": request_id},
        lambda: NextGameCommunityService.close_request(session, int(admin.tg_id), request_id))


@router.put("/settings")
async def settings(body: Settings, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    async def update_settings():
        company = await NextGameService._owned_company(session, int(admin.tg_id))
        row = await profile(session, company.id)
        row.auto_upgrade = body.auto_upgrade
        await session.flush()
        return {"success": True, "settings": {"auto_upgrade": row.auto_upgrade}}
    return await mutate(session, admin, key, "/next-game/settings", body.model_dump(), update_settings)


@router.get("/admin")
async def admin_panel(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    from backend.natbirzha.api.creator_auth import get_creator_tg_ids
    data = await NextGameAdminService.snapshot(session)
    data["can_force_bankruptcy"] = int(admin.tg_id) in get_creator_tg_ids()
    return data


@router.post("/admin/operations")
async def admin_operation(body: AdminOperation, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/next-game/admin/operations", body.model_dump(),
        lambda: NextGameAdminService.operate(session, int(admin.tg_id), body.action, body.company_id,
            body.value, body.item_id, body.note))
