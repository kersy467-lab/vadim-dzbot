"""Creator-only bond reads and serialized idempotent bond mutations."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_bond_service import NextGameBondService
from backend.natbirzha.services.next_game_bond_read_service import NextGameBondReadService

router = APIRouter(prefix="/next-game/bonds", tags=["Next Game Reserve Bonds"])


class BuyBond(BaseModel):
    series_id: int = Field(ge=1, le=3)
    units: int = Field(ge=1, le=10000)


class ListBond(BaseModel):
    holding_id: int = Field(gt=0)
    units: int = Field(ge=1, le=10000)
    unit_price: float = Field(gt=0, allow_inf_nan=False)


class BuyListing(BaseModel):
    units: int = Field(ge=1, le=10000)


async def mutate(session, admin, key, endpoint, payload, action):
    if not key or not key.strip():
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    key = key.strip()[:128]
    try:
        await NextGameMarketService.lock_orderbook(session)
        cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, key, payload)
        if cached:
            return cached[1]
        result = await action()
        return await IdempotencyService.commit_response(session, admin.id, endpoint, key, payload, result)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise


@router.get("")
async def get_bonds(admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    try:
        result = await NextGameBondReadService.snapshot(session, int(admin.tg_id))
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise


@router.post("/buy")
async def buy_bonds(request: BuyBond, key: str | None = Header(None, alias="Idempotency-Key"),
                    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/api/natbirzha/next-game/bonds/buy", request.model_dump(),
        lambda: NextGameBondService.buy(session, int(admin.tg_id), request.series_id, request.units))


@router.post("/listings")
async def list_bonds(request: ListBond, key: str | None = Header(None, alias="Idempotency-Key"),
                     admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, "/api/natbirzha/next-game/bonds/listings", request.model_dump(),
        lambda: NextGameBondService.list(session, int(admin.tg_id), request.holding_id, request.units, request.unit_price))


@router.post("/listings/{listing_id}/buy")
async def buy_bond_listing(listing_id: int, request: BuyListing,
    key: str | None = Header(None, alias="Idempotency-Key"), admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, f"/api/natbirzha/next-game/bonds/listings/{listing_id}/buy",
        {"listing_id": listing_id, **request.model_dump()},
        lambda: NextGameBondService.buy_listing(session, int(admin.tg_id), listing_id, request.units))


@router.delete("/listings/{listing_id}")
async def cancel_bond_listing(listing_id: int, key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator), session: AsyncSession = Depends(get_db_session)):
    return await mutate(session, admin, key, f"/api/natbirzha/next-game/bonds/listings/{listing_id}",
        {"listing_id": listing_id}, lambda: NextGameBondService.cancel_listing(session, int(admin.tg_id), listing_id))


__all__ = ["router"]
