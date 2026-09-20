from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.api.game_rooms import game_manager

router = APIRouter(tags=["games"])

@router.post("/games/room/{room_id}/bot")
async def add_bot_to_coop_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Добавляет бота в кооп-рейд."""
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    ok, msg = game_manager.add_bot_to_coop(room_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    room = game_manager.get_room(room_id)
    return room.to_dict(viewer_tg_id=viewer_tg_id)

@router.post("/games/room/{room_id}/resign")
async def resign_game_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Сдача в партии."""
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    ok, msg = game_manager.resign_room(room_id, viewer_tg_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    room = game_manager.get_room(room_id)
    return room.to_dict(viewer_tg_id=viewer_tg_id)

@router.post("/games/room/{room_id}/rematch")
async def rematch_game_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Запрос или подтверждение реванша."""
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    ok, msg = game_manager.request_rematch(room_id, viewer_tg_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    room = game_manager.get_room(room_id)
    return room.to_dict(viewer_tg_id=viewer_tg_id)

@router.post("/games/room/{room_id}/cancel")
async def cancel_game_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Отмена вызова создателем."""
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    game_manager.cancel_room(room_id, viewer_tg_id)
    return {"status": "canceled"}
