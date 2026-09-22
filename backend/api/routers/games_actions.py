from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import has_full_access
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.api.game_rooms import game_manager
from backend.api.ege_rating import build_ege_room_payload
from backend.db.session import get_db_session

router = APIRouter(tags=["games"])
_EGE_TYPES = {"ege_stress_duel", "ege_vocabulary_duel"}


def _room_for_user(room_id: str, user: Optional[User]):
    room = game_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not has_full_access(user) and getattr(room, "game_type", "") not in _EGE_TYPES:
        raise HTTPException(status_code=403, detail="Обычным игрокам доступны только ЕГЭ-дуэли")
    return room


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
    return room.to_dict(viewer_tg_id=viewer_tg_id)


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
    return room.to_dict(viewer_tg_id=viewer_tg_id)


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
    return await build_ege_room_payload(session, room, viewer_tg_id)


@router.post("/games/room/{room_id}/cancel")
async def cancel_game_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    _room_for_user(room_id, user)
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    if not game_manager.cancel_room(room_id, viewer_tg_id):
        raise HTTPException(status_code=400, detail="Отменить комнату может только создатель")
    return {"status": "canceled"}
