"""Manual creator liquidation and authenticated recovery/asset purchases."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.services.access_control import get_creator_tg_ids
from backend.natbirzha.services.next_game_bankruptcy_service import NextGameBankruptcyService as Bankruptcy

router = APIRouter(prefix="/next-game", tags=["Next Game Recovery"])


class RecoveryRequest(BaseModel):
    restart: StrictBool


class ForceRequest(BaseModel):
    company_id: int = Field(gt=0)
    note: str = Field(min_length=5, max_length=500)
    confirm: StrictBool


async def read(session, operation):
    try:
        result = await operation()
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise


@router.get("/recovery")
async def get_recovery(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await read(session, lambda: Bankruptcy.recovery_snapshot(session, int(admin.tg_id)))


@router.post("/recovery")
async def recover(request: RecoveryRequest, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/api/natbirzha/next-game/recovery", request.model_dump(),
        lambda: Bankruptcy.recover(session, int(admin.tg_id), request.restart))


@router.post("/admin/bankruptcy")
async def force(request: ForceRequest, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    if int(admin.tg_id) not in get_creator_tg_ids():
        raise HTTPException(status_code=403, detail="Банкротство объявляет только Создатель")
    if request.confirm is not True:
        raise HTTPException(status_code=400, detail="Подтвердите изъятие имущества и списание долгов")
    return await mutate(session, admin, key, "/api/natbirzha/next-game/admin/bankruptcy", request.model_dump(),
        lambda: Bankruptcy.force(session, request.company_id, request.note, int(admin.tg_id)))


@router.get("/liquidation")
async def get_liquidation(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await read(session, lambda: Bankruptcy.liquidation_snapshot(session, int(admin.tg_id)))


@router.post("/liquidation/{lot_id}/buy")
async def buy(lot_id: int, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, f"/api/natbirzha/next-game/liquidation/{lot_id}/buy", {"lot_id": lot_id},
        lambda: Bankruptcy.buy_lot(session, int(admin.tg_id), lot_id))
