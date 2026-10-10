"""Authenticated next-game commodity browser, item book and liquidity reads."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.next_game_market_browser_service import NextGameMarketBrowserService
from backend.natbirzha.services.next_game_service import NextGameService

router = APIRouter(prefix="/next-game/market", tags=["Next Game Market"])


async def _read_company(session, owner_tg_id, action, *args):
    try:
        await NextGameService._lock_treasury_for_sqlite(session)
        await NextGameService.settle_company(session, owner_tg_id)
        result = await action(session, owner_tg_id, *args)
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise


@router.get("/catalog")
async def market_catalog(admin: User = Depends(get_current_creator),
                         session: AsyncSession = Depends(get_db_session)):
    return await _read_company(session, int(admin.tg_id), NextGameMarketBrowserService.catalog)


@router.get("/items/{item_id}")
async def market_item(item_id: str, admin: User = Depends(get_current_creator),
                      session: AsyncSession = Depends(get_db_session)):
    return await _read_company(session, int(admin.tg_id), NextGameMarketBrowserService.item, item_id)


@router.get("/liquidity")
async def market_liquidity(admin: User = Depends(get_current_creator),
                           session: AsyncSession = Depends(get_db_session)):
    return await NextGameMarketBrowserService.liquidity(session)


__all__ = ["router"]
