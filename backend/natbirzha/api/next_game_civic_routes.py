"""Authenticated civic reads and idempotent reserve transfers."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.services.access_control import get_creator_tg_ids
from backend.natbirzha.services.next_game_civic_service import NextGameCivicService

router = APIRouter(prefix="/next-game/civic", tags=["Next Game Civic"])


class FulfillRequest(BaseModel):
    quantity: float = Field(gt=0, allow_inf_nan=False)


class EventRequest(BaseModel):
    sector_id: str = Field(min_length=1, max_length=48)
    duration_hours: float = Field(gt=0, le=24, allow_inf_nan=False)


@router.get("")
async def snapshot(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    try:
        result = await NextGameCivicService.snapshot(session, int(admin.tg_id))
        result["can_create_event"] = bool(int(admin.tg_id) in get_creator_tg_ids())
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise


@router.post("/taxes/{tax_id}/pay")
async def pay(tax_id: int, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, f"/api/natbirzha/next-game/civic/taxes/{tax_id}/pay",
        {"tax_id": tax_id}, lambda: NextGameCivicService.pay_tax(session, int(admin.tg_id), tax_id))


@router.post("/orders/{order_id}/fulfill")
async def fulfill(order_id: int, request: FulfillRequest, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, f"/api/natbirzha/next-game/civic/orders/{order_id}/fulfill",
        {"order_id": order_id, **request.model_dump()},
        lambda: NextGameCivicService.fulfill(session, int(admin.tg_id), order_id, request.quantity))


@router.post("/events")
async def event(request: EventRequest, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    if int(admin.tg_id) not in get_creator_tg_ids():
        raise HTTPException(status_code=403, detail="События запускает только Создатель")
    return await mutate(session, admin, key, "/api/natbirzha/next-game/civic/events", request.model_dump(),
        lambda: NextGameCivicService.create_event(session, int(admin.tg_id), request.sector_id, request.duration_hours))
