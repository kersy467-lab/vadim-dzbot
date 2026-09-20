"""Public read-only company rankings."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.leaderboard_service import LeaderboardService


router = APIRouter(prefix="/leaderboard", tags=["Natbirzha Leaderboard"])


@router.get("")
async def get_leaderboard(
    category: str = Query(default="assets"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await LeaderboardService.get_leaderboard(
            session, company.id, category=category, page=page, page_size=page_size
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
