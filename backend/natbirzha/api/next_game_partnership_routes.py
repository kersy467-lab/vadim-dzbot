"""Authenticated and idempotent supply and co-owned factory commands."""
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.services.next_game_partnership_service import NextGamePartnershipService as Service

router = APIRouter(prefix="/next-game/partnerships", tags=["Next Game Partnerships"])


class SupplyRequest(BaseModel):
    counterparty_id: int = Field(ge=1)
    item_id: str = Field(min_length=1, max_length=64)
    quantity: float = Field(gt=0, le=100_000)
    unit_price: float = Field(gt=0, le=1_000_000)
    rate_per_hour: float = Field(gt=0, le=100_000)
    duration_hours: int = Field(ge=1, le=720)


class ProjectRequest(BaseModel):
    counterparty_id: int = Field(ge=1)
    branch_id: str = Field(min_length=1, max_length=64)


class ResponseRequest(BaseModel):
    accept: bool


@router.get("")
async def read(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    try:
        result = await Service.snapshot(session, int(admin.tg_id))
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/supply")
async def supply(request: SupplyRequest, key: str | None = Header(None, alias="Idempotency-Key"),
                 admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/api/natbirzha/next-game/partnerships/supply", request.model_dump(),
                        lambda: Service.create_supply(session, int(admin.tg_id), **request.model_dump()))


@router.post("/projects")
async def project(request: ProjectRequest, key: str | None = Header(None, alias="Idempotency-Key"),
                  admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/api/natbirzha/next-game/partnerships/projects", request.model_dump(),
                        lambda: Service.create_project(session, int(admin.tg_id), **request.model_dump()))


@router.post("/{kind}/{id}/respond")
async def respond(kind: Literal["supply", "projects"], id: int, request: ResponseRequest,
                  key: str | None = Header(None, alias="Idempotency-Key"),
                  admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    payload = {"kind": kind, "id": id, "accept": request.accept}
    return await mutate(session, admin, key, "/api/natbirzha/next-game/partnerships/respond", payload,
                        lambda: Service.respond(session, int(admin.tg_id), **payload))


@router.post("/{kind}/{id}/cancel")
async def cancel(kind: Literal["supply", "projects"], id: int,
                 key: str | None = Header(None, alias="Idempotency-Key"),
                 admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    payload = {"kind": kind, "id": id}
    return await mutate(session, admin, key, "/api/natbirzha/next-game/partnerships/cancel", payload,
                        lambda: Service.cancel(session, int(admin.tg_id), **payload))


__all__ = ["router"]
