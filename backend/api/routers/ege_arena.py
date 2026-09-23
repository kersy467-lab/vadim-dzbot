"""Public EGE Arena profile, nickname and leaderboard API."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_webapp_user, get_optional_webapp_user
from backend.api.ege_matchmaking import get_matchmaking_candidate_ids, send_matchmaking_notifications
from backend.api.ege_rating import build_ege_room_payload
from backend.api.game_rooms import game_manager
from backend.api.routers.games_rpg_hooks import get_public_webapp_url
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


@router.post("/matchmaking/search")
async def search_ege_duel(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: dict = Body(default_factory=dict),
    user: User = Depends(get_current_webapp_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a public EGE duel search and notify the ranked Arena roster."""
    if not isinstance(payload, dict):
        payload = {}
    game_type = str(payload.get("game_type") or "ege_stress_duel").strip().lower()
    if game_type not in {"ege_stress_duel", "ege_vocabulary_duel"}:
        raise HTTPException(status_code=400, detail="Выберите режим ЕГЭ-дуэли")
    if not user.ege_nickname:
        raise HTTPException(status_code=401, detail="Сначала установите игровой ник")

    host_tg_id = int(user.tg_id)
    game_manager.cleanup()
    active_room = next((
        room for room in game_manager.rooms.values()
        if getattr(room, "matchmaking_search", False)
        and room.host_tg_id == host_tg_id
        and room.game_type == game_type
        and room.status == "waiting"
        and room.opponent_tg_id is None
    ), None)
    if active_room:
        return await build_ege_room_payload(session, active_room, host_tg_id)

    recipient_ids = await get_matchmaking_candidate_ids(session, host_tg_id)
    if not recipient_ids:
        raise HTTPException(
            status_code=409,
            detail="Пока нет игроков рейтинга с включёнными уведомлениями для поиска дуэли.",
        )

    from backend.bot.bot import get_current_bot
    bot = get_current_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Уведомления Telegram сейчас недоступны")

    room = game_manager.create_room(
        host_tg_id=host_tg_id,
        host_name=user.ege_nickname,
        opponent_tg_id=None,
        opponent_name=None,
        game_type=game_type,
    )
    room.matchmaking_search = True
    background_tasks.add_task(
        send_matchmaking_notifications,
        bot,
        room,
        recipient_ids,
        get_public_webapp_url(request),
    )
    state = await build_ege_room_payload(session, room, host_tg_id)
    state["notifications_queued"] = len(recipient_ids)
    return state
