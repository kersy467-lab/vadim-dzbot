import asyncio
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import has_full_access
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.api.game_rooms import game_manager
from backend.api.ege_rating import build_ege_room_payload
from backend.db.session import get_db_session
from backend.api.routers.games_ws import room_ws_manager

router = APIRouter(tags=["games"])
_EGE_TYPES = {"ege_stress_duel", "ege_vocabulary_duel"}


def _room_for_user(room_id: str, user: Optional[User]):
    room = game_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not has_full_access(user) and getattr(room, "game_type", "") not in _EGE_TYPES:
        raise HTTPException(status_code=403, detail="Обычным игрокам доступны только ЕГЭ-дуэли")
    return room


@router.post("/games/bot")
async def create_bot_game(
    request: Request,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Создает игру против бота (шашки или шахматы)."""
    if not payload:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    if not isinstance(payload, dict):
        payload = {}

    game_type = str(payload.get("game_type") or "checkers").strip().lower()
    host_color = str(payload.get("host_color") or "white").strip().lower()
    if host_color not in ["white", "black", "random"]:
        host_color = "white"

    if not has_full_access(user):
        raise HTTPException(status_code=403, detail="Обычным игрокам доступны только ЕГЭ-дуэли")
    host_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    host_name = user.display_name if user else payload.get("host_name", "Игрок")

    from backend.api.game_rooms import chess
    if game_type == "chess" and chess is None:
        raise HTTPException(
            status_code=503,
            detail="Шахматный режим загружается на сервере. Пожалуйста, подождите минуту!"
        )

    room = game_manager.create_bot_room(
        host_tg_id=host_tg_id,
        host_name=host_name,
        game_type=game_type,
        host_color=host_color
    )
    return room.to_dict(viewer_tg_id=host_tg_id)


@router.post("/games/room/{room_id}/bot")
async def add_bot_to_coop_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    room = _room_for_user(room_id, user)
    if getattr(room, "game_type", "") in _EGE_TYPES:
        raise HTTPException(status_code=400, detail="Бот-соперник для рейтинговой ЕГЭ-дуэли не поддерживается")
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    ok, msg = game_manager.add_bot_to_coop(room_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    res = room.to_dict(viewer_tg_id=viewer_tg_id)
    if room_ws_manager.has_clients(room_id):
        asyncio.create_task(room_ws_manager.broadcast_room(room_id, {"type": "state", "payload": res}))
    return res


@router.post("/games/room/{room_id}/resign")
async def resign_game_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    room = _room_for_user(room_id, user)
    if getattr(room, "game_type", "") in _EGE_TYPES:
        raise HTTPException(status_code=400, detail="В ЕГЭ-дуэли нельзя сдаться: завершите задания")
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    ok, msg = game_manager.resign_room(room_id, viewer_tg_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    res = room.to_dict(viewer_tg_id=viewer_tg_id)
    if room_ws_manager.has_clients(room_id):
        asyncio.create_task(room_ws_manager.broadcast_room(room_id, {"type": "state", "payload": res}))
    return res


@router.post("/games/room/{room_id}/rematch")
async def rematch_game_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session),
):
    room = _room_for_user(room_id, user)
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    ok, msg = game_manager.request_rematch(room_id, viewer_tg_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    payload_data = await build_ege_room_payload(session, room, viewer_tg_id)
    if room_ws_manager.has_clients(room_id):
        asyncio.create_task(room_ws_manager.broadcast_room(room_id, {"type": "state", "payload": payload_data}))
    return payload_data


@router.post("/games/room/{room_id}/cancel")
async def cancel_game_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    room = _room_for_user(room_id, user)
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    if not game_manager.cancel_room(room_id, viewer_tg_id):
        raise HTTPException(status_code=400, detail="Отменить комнату может только создатель")

    from backend.bot.bot import get_current_bot
    from backend.api.routers.games_rpg_hooks import update_canceled_invite_message
    from backend.api.ege_matchmaking import on_opponent_joined_matchmaking
    bot = get_current_bot()
    if bot:
        try:
            await update_canceled_invite_message(bot, room)
        except Exception:
            pass
    on_opponent_joined_matchmaking(room, keep_participants=False)
    if room_ws_manager.has_clients(room_id):
        asyncio.create_task(room_ws_manager.broadcast_room(room_id, {"type": "state", "payload": {"status": "canceled"}}))
    return {"status": "canceled"}


