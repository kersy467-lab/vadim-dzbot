"""
FastAPI роутер игры «Блэкджек (21 очко)» на монеты.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Body

from backend.db.models import User
from backend.db.session import async_session_factory
from backend.db.crud.users import add_user_coins, get_user_by_tg_id
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.bot.game_blackjack import BlackjackGame
from .state import get_session, create_session, clear_session

router = APIRouter(prefix="/blackjack", tags=["blackjack"])


async def _resolve_user_and_check_ecosystem(
    request: Request,
    user: Optional[User],
    payload: Optional[Dict[str, Any]] = None,
) -> tuple[int, User]:
    viewer_id = _extract_viewer_tg_id(user, request, payload=payload)
    if not viewer_id:
        raise HTTPException(status_code=401, detail="Требуется авторизация через Telegram Mini App")

    async with async_session_factory() as session:
        db_user = await get_user_by_tg_id(session, viewer_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if not bool(getattr(db_user, "currency_ecosystem_enabled", False)):
            raise HTTPException(
                status_code=400,
                detail="Включите игровую экосистему в настройках бота для игры в 21 Очко"
            )
        return viewer_id, db_user


@router.get("/state")
async def blackjack_state(
    request: Request,
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Получение текущего состояния раздачи и баланса игрока."""
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user)
    sess = get_session(viewer_id)
    state = sess["game"].to_dict() if sess else None
    return {
        "ok": True,
        "state": state,
        "coins": db_user.coins or 0,
    }


@router.post("/deal")
async def blackjack_deal(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """
    Начало новой раздачи в Блэкджек.
    payload: {"stake": 25}
    """
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)

    stake = int(payload.get("stake", 10))
    if stake <= 0:
        raise HTTPException(status_code=400, detail="Ставка должна быть больше 0")

    if (db_user.coins or 0) < stake:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно монет для ставки. Ваш баланс: {db_user.coins or 0} 🪙"
        )

    # Списываем ставку из базы данных
    async with async_session_factory() as session:
        await add_user_coins(session, viewer_id, -stake)
        refreshed_user = await get_user_by_tg_id(session, viewer_id)
        user_coins = refreshed_user.coins or 0

    sess = create_session(viewer_id, stake)
    game: BlackjackGame = sess["game"]
    state = game.deal(stake)

    # Если выпал натуральный Блэкджек или ничья с первых 2 карт
    if game.phase == "done" and not sess["settled"]:
        if game.payout > 0:
            async with async_session_factory() as session:
                await add_user_coins(session, viewer_id, game.payout)
                refreshed_user = await get_user_by_tg_id(session, viewer_id)
                user_coins = refreshed_user.coins or 0
        sess["settled"] = True

    return {
        "ok": True,
        "state": state,
        "coins": user_coins,
    }


@router.post("/hit")
async def blackjack_hit(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Игрок берет дополнительную карту («Еще»)."""
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)
    sess = get_session(viewer_id)
    if not sess or sess["game"].phase != "player_turn":
        raise HTTPException(status_code=400, detail="Нет активной раздачи")

    game: BlackjackGame = sess["game"]
    state = game.hit()
    user_coins = db_user.coins or 0

    if game.phase == "done" and not sess["settled"]:
        if game.payout > 0:
            async with async_session_factory() as session:
                await add_user_coins(session, viewer_id, game.payout)
                refreshed_user = await get_user_by_tg_id(session, viewer_id)
                user_coins = refreshed_user.coins or 0
        sess["settled"] = True

    return {
        "ok": True,
        "state": state,
        "coins": user_coins,
    }


@router.post("/stand")
async def blackjack_stand(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Игрок останавливается («Хватит»). Ход переходит к дилеру."""
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)
    sess = get_session(viewer_id)
    if not sess or sess["game"].phase != "player_turn":
        raise HTTPException(status_code=400, detail="Нет активной раздачи")

    game: BlackjackGame = sess["game"]
    state = game.stand()
    user_coins = db_user.coins or 0

    if game.phase == "done" and not sess["settled"]:
        if game.payout > 0:
            async with async_session_factory() as session:
                await add_user_coins(session, viewer_id, game.payout)
                refreshed_user = await get_user_by_tg_id(session, viewer_id)
                user_coins = refreshed_user.coins or 0
        sess["settled"] = True

    return {
        "ok": True,
        "state": state,
        "coins": user_coins,
    }


@router.post("/double")
async def blackjack_double(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Удвоение ставки («Удвоить»): +1 карта и завершение хода."""
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)
    sess = get_session(viewer_id)
    if not sess or sess["game"].phase != "player_turn":
        raise HTTPException(status_code=400, detail="Нет активной раздачи")

    game: BlackjackGame = sess["game"]
    if len(game.player_cards) != 2:
        raise HTTPException(status_code=400, detail="Удвоить ставку можно только на первых двух картах")

    additional_stake = game.original_stake
    if (db_user.coins or 0) < additional_stake:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно монет для удвоения (требуется еще {additional_stake} 🪙)"
        )

    # Списываем дополнительную ставку
    async with async_session_factory() as session:
        await add_user_coins(session, viewer_id, -additional_stake)

    state = game.double_down()

    async with async_session_factory() as session:
        if game.phase == "done" and not sess["settled"] and game.payout > 0:
            await add_user_coins(session, viewer_id, game.payout)
            sess["settled"] = True
        refreshed_user = await get_user_by_tg_id(session, viewer_id)
        user_coins = refreshed_user.coins or 0

    return {
        "ok": True,
        "state": state,
        "coins": user_coins,
    }


# ==========================================
# Многопользовательский стол (2–4 игрока)
# ==========================================
from fastapi import WebSocket, WebSocketDisconnect
from .table_state import (
    get_table, list_open_tables, create_table, join_table, leave_table,
    place_table_bet, start_table_deal, player_table_action, broadcast_table
)


@router.get("/tables")
async def get_blackjack_tables():
    """Список открытых столов Блэкджек для лобби."""
    return {"ok": True, "tables": list_open_tables()}


@router.post("/table/new")
async def blackjack_table_new(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Создать новый общий стол (на 2–4 игрока)."""
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)
    max_players = int(payload.get("max_players", 4))
    min_stake = int(payload.get("min_stake", 10))
    entry = create_table(viewer_id, db_user.display_name or db_user.full_name, max_players, min_stake)
    return {"ok": True, "table_id": entry["game"].table_id, "state": entry["game"].to_dict()}


@router.post("/table/join")
async def blackjack_table_join(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Сесть за общий стол."""
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)
    table_id = payload.get("table_id", "")
    res = join_table(table_id, viewer_id, db_user.display_name or db_user.full_name)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Не удалось войти за стол"))
    await broadcast_table(table_id)
    return {"ok": True, "state": res["state"]}


@router.post("/table/leave")
async def blackjack_table_leave(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Покинуть общий стол."""
    viewer_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    table_id = payload.get("table_id", "")
    if table_id and viewer_id:
        await leave_table(table_id, viewer_id)
    return {"ok": True}


@router.post("/table/bet")
async def blackjack_table_bet(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Сделать ставку за общим столом."""
    viewer_id, _ = await _resolve_user_and_check_ecosystem(request, user, payload=payload)
    table_id = payload.get("table_id", "")
    stake = int(payload.get("stake", 0))
    res = await place_table_bet(table_id, viewer_id, stake)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Ошибка ставки"))
    return res


@router.post("/table/deal")
async def blackjack_table_deal(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Начать раздачу карт за столом."""
    table_id = payload.get("table_id", "")
    res = await start_table_deal(table_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Не удалось начать раздачу"))
    return res


@router.post("/table/action")
async def blackjack_table_action_endpoint(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Действие игрока за столом: hit / stand / double."""
    viewer_id, _ = await _resolve_user_and_check_ecosystem(request, user, payload=payload)
    table_id = payload.get("table_id", "")
    action = payload.get("action", "")
    res = await player_table_action(table_id, viewer_id, action)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Недопустимый ход"))
    return res


@router.get("/table/{table_id}")
async def blackjack_table_state(table_id: str):
    """Получить текущее состояние стола."""
    entry = get_table(table_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Стол не найден")
    return {"ok": True, "state": entry["game"].to_dict()}


@router.websocket("/ws/{table_id}/{user_id}")
async def blackjack_table_ws(websocket: WebSocket, table_id: str, user_id: int):
    """Вебсокет синхронизации общего стола в реальном времени."""
    await websocket.accept()
    entry = get_table(table_id)
    if not entry:
        await websocket.send_text('{"type":"error","message":"Стол не найден"}')
        await websocket.close()
        return

    entry.setdefault("connections", {})[user_id] = websocket
    import json
    await websocket.send_text(json.dumps({"type": "table_state", "state": entry["game"].to_dict()}))

    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        entry.get("connections", {}).pop(user_id, None)

