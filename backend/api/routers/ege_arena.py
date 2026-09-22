"""Public EGE Arena profile, nickname and leaderboard API."""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_webapp_user, get_optional_webapp_user
from backend.db.crud import get_user_by_ege_nickname, set_ege_nickname
from backend.db.models import User
from backend.db.session import get_db_session
from backend.ege.ranking import get_leaderboard, get_player_profile

router = APIRouter(prefix="/ege", tags=["ege-arena"])


@router.get("/profile")
async def get_own_ege_profile(
    user: User = Depends(get_current_webapp_user),
    session: AsyncSession = Depends(get_db_session),
):
    return await get_player_profile(session, user)


@router.get("/profile/{nickname}")
async def get_ege_profile_by_nickname(
    nickname: str,
    _: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session),
):
    user = await get_user_by_ege_nickname(session, nickname)
    if not user:
        raise HTTPException(status_code=404, detail=f'Игрок с ником "{nickname}" не найден.')
    return await get_player_profile(session, user)


@router.post("/nickname")
async def update_ege_nickname(
    payload: dict = Body(default_factory=dict),
    user: User = Depends(get_current_webapp_user),
    session: AsyncSession = Depends(get_db_session),
):
    ok, message = await set_ege_nickname(session, user, str(payload.get("nickname") or ""))
    if not ok:
        raise HTTPException(status_code=409 if "занят" in message else 400, detail=message)
    return await get_player_profile(session, user)


@router.get("/players")
async def get_ege_players_for_duel(
    user: User = Depends(get_current_webapp_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Cached public Arena roster; separate from legacy full-access classmates."""
    rows = await get_leaderboard(session)
    return [
        {**row, "name": row["nickname"]}
        for row in rows
        if int(row["tg_id"]) != int(user.tg_id)
    ]


@router.get("/leaderboard")
async def get_ege_leaderboard(
    _: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session),
):
    rows = await get_leaderboard(session)
    return {"refresh_seconds": 600, "players": rows}
