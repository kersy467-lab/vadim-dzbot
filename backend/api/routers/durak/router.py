"""
FastAPI роутер игры «Дурак» (эндпоинты и вебсокеты).
"""
import asyncio
import json
import uuid as _uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, Body, WebSocket, WebSocketDisconnect

from backend.db.models import User
from backend.db.session import async_session_factory
from backend.db.crud.users import add_user_coins, get_currency_leaderboard, get_user_by_tg_id
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.bot.game_durak import DurakGame

from .state import (
    _durak_rooms,
    _get_or_404,
    _durak_bot_auto_move,
    _durak_check_settlement,
    _durak_broadcast,
    _durak_leave_room,
)

router = APIRouter(tags=["durak"])


@router.get("/durak/leaderboard")
@router.get("/casino/leaderboard")
async def durak_leaderboard():
    """Возвращает топ студентов по монетам среди включивших игровую экосистему."""
    async with async_session_factory() as session:
        leaders = await get_currency_leaderboard(session, limit=20)
    return {"leaderboard": leaders}


@router.post("/durak/new")
async def durak_new(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """
    Создание новой игры или комнаты «Дурак».
    mode: "bot" | "online"
    players_count: 2..6
    stake: int >= 0 (ставка на монеты)
    """
    viewer_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    if not viewer_id:
        raise HTTPException(status_code=400, detail="user_id обязателен")

    mode = payload.get("mode", "bot")
    players_count = int(payload.get("players_count", 2))
    if not (2 <= players_count <= 6):
        raise HTTPException(status_code=400, detail="players_count должен быть от 2 до 6")

    stake = max(0, int(payload.get("stake", 0)))

    # Проверка баланса и списание ставки
    if stake > 0:
        async with async_session_factory() as session:
            db_user = await get_user_by_tg_id(session, viewer_id)
            if not db_user:
                raise HTTPException(status_code=400, detail="Пользователь не найден")
            if not bool(getattr(db_user, "currency_ecosystem_enabled", False)):
                raise HTTPException(status_code=400, detail="Включите игровую экосистему в настройках бота для игры со ставками")
            if (db_user.coins or 0) < stake:
                raise HTTPException(status_code=400, detail=f"Недостаточно монет. Ваш баланс: {db_user.coins or 0} 🪙")
            await add_user_coins(session, viewer_id, -stake)

    room_id = str(_uuid.uuid4())[:8]

    if mode == "bot":
        bot_id = -1
        game = DurakGame(player_ids=[viewer_id, bot_id], bot_indices=[bot_id], stake=stake)
        _durak_rooms[room_id] = {
            "game": game,
            "mode": "bot",
            "players": [viewer_id, bot_id],
            "stake": stake,
            "settled": False,
            "connections": {},
        }
        _durak_bot_auto_move(room_id)
        await _durak_check_settlement(room_id)
        return {"room_id": room_id, "state": game.to_state(for_player_id=viewer_id)}
    else:
        _durak_rooms[room_id] = {
            "game": None,
            "mode": "online",
            "players": [viewer_id],
            "players_count": players_count,
            "stake": stake,
            "settled": False,
            "connections": {},
        }
        return {"room_id": room_id, "status": "waiting", "players": [viewer_id], "stake": stake}


@router.post("/durak/join")
async def durak_join(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Присоединение к онлайн-комнате."""
    viewer_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    room_id = payload.get("room_id", "")
    room = _get_or_404(room_id)

    if room["mode"] != "online":
        raise HTTPException(status_code=400, detail="Комната не в режиме онлайн")
    if viewer_id in room["players"]:
        state = room["game"].to_state(for_player_id=viewer_id) if room.get("game") else None
        return {"room_id": room_id, "status": "already_joined", "players": room["players"], "state": state}

    if room.get("game") is not None:
        raise HTTPException(status_code=400, detail="Игра в этой комнате уже началась")

    stake = room.get("stake", 0)
    if stake > 0:
        async with async_session_factory() as session:
            db_user = await get_user_by_tg_id(session, viewer_id)
            if not db_user:
                raise HTTPException(status_code=400, detail="Пользователь не найден")
            if not bool(getattr(db_user, "currency_ecosystem_enabled", False)):
                raise HTTPException(status_code=400, detail="Включите игровую экосистему в настройках бота для игры со ставками")
            if (db_user.coins or 0) < stake:
                raise HTTPException(status_code=400, detail=f"Для входа требуется ставка {stake} 🪙. Ваш баланс: {db_user.coins or 0} 🪙")
            await add_user_coins(session, viewer_id, -stake)

    room["players"].append(viewer_id)
    needed = room["players_count"]

    if len(room["players"]) >= needed:
        game = DurakGame(player_ids=room["players"], stake=stake)
        room["game"] = game
        asyncio.create_task(_durak_broadcast(room_id))
        return {"room_id": room_id, "status": "started", "state": game.to_state(for_player_id=viewer_id)}

    asyncio.create_task(_durak_broadcast(room_id))
    return {"room_id": room_id, "status": "waiting", "players": room["players"], "stake": stake}


@router.post("/durak/leave")
@router.post("/durak/cancel")
async def durak_leave_endpoint(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Выход из комнаты или отмена ожидания с возвратом ставки."""
    viewer_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    room_id = payload.get("room_id", "")
    if not room_id:
        return {"ok": True, "status": "left"}
    return await _durak_leave_room(room_id, viewer_id)


@router.get("/durak/state/{room_id}")
async def durak_state(
    room_id: str,
    request: Request,
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Получение текущего состояния игры."""
    room = _get_or_404(room_id)
    viewer_id = _extract_viewer_tg_id(user, request) or 0

    if not room.get("game"):
        return {"room_id": room_id, "status": "waiting", "players": room["players"], "stake": room.get("stake", 0)}

    return {
        "room_id": room_id,
        "status": "playing" if room["game"].phase != "done" else "finished",
        "state": room["game"].to_state(for_player_id=viewer_id),
    }


@router.post("/durak/move")
async def durak_move(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Совершить ход в Дураке: action = attack|defend|take|pass"""
    viewer_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    room_id = payload.get("room_id", "")
    room = _get_or_404(room_id)

    if not room.get("game"):
        raise HTTPException(status_code=400, detail="Игра ещё не началась")

    game = room["game"]
    action = payload.get("action", "")

    result: dict
    if action == "attack":
        card = payload.get("card")
        if not card:
            raise HTTPException(status_code=400, detail="Выберите карту для атаки")
        result = game.attack(viewer_id, card)
    elif action == "defend":
        attack_card = payload.get("attack_card")
        defend_card = payload.get("card")
        if not attack_card or not defend_card:
            raise HTTPException(status_code=400, detail="Выберите атакующую и защитную карту")
        result = game.defend(viewer_id, attack_card, defend_card)
    elif action == "take":
        result = game.take(viewer_id)
    elif action == "pass":
        result = game.pass_attack(viewer_id)
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестное действие: {action}")

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Ошибка хода"))

    if room["mode"] == "bot":
        _durak_bot_auto_move(room_id)

    # Проверка завершения партии и выплата банка
    await _durak_check_settlement(room_id)

    asyncio.create_task(_durak_broadcast(room_id))

    return {"ok": True, "state": game.to_state(for_player_id=viewer_id)}


@router.websocket("/ws/durak/{room_id}/{user_id}")
async def durak_ws(websocket: WebSocket, room_id: str, user_id: int):
    """Вебсокет для онлайн-синхронизации ходов и лобби ожидания."""
    await websocket.accept()

    room = _durak_rooms.get(room_id)
    if not room:
        await websocket.send_text(json.dumps({"type": "error", "message": "Комната не найдена"}))
        await websocket.close()
        return

    room.setdefault("connections", {})[user_id] = websocket

    if room.get("game"):
        state = room["game"].to_state(for_player_id=user_id)
        await websocket.send_text(json.dumps({"type": "state", "state": state}))
    else:
        await websocket.send_text(json.dumps({
            "type": "waiting",
            "players": room["players"],
            "stake": room.get("stake", 0)
        }))

    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        room.get("connections", {}).pop(user_id, None)
