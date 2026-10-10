"""Server-gated rankings for the 2.0 closed playtest."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.next_game_competition_service import NextGameCompetitionService


router = APIRouter(prefix="/next-game/competition", tags=["Natbirzha Next Game Competition"])


@router.get("")
async def get_competition(
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        result = await NextGameCompetitionService.snapshot(session, int(admin.tg_id))
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise


__all__ = ["router"]
