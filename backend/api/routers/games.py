import asyncio
import html
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.api.game_rooms import game_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["games"])

@router.get("/games/classmates")
async def get_classmates_for_game(
    request: Request,
    tg_user_id: Optional[int] = Query(None),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Возвращает список одноклассников для вызова на онлайн-дуэль."""
    from backend.db.crud import get_active_users
    users = await get_active_users(session)
    current_tg_id = _extract_viewer_tg_id(user, request, query_tg_id=tg_user_id) or 0

    return [
        {
            "id": u.id,
            "tg_id": u.tg_id,
            "name": u.display_name,
            "role": u.role
        }
        for u in users
        if u.tg_id != current_tg_id and u.tg_id > 0
    ]


from backend.api.routers.games_rpg_hooks import (
    get_public_webapp_url as _get_public_webapp_url,
    send_game_invite_notification as _send_game_invite_notification,
)


@router.post("/games/local")
async def create_local_game(
    request: Request,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    user: Optional[User] = Depends(get_optional_webapp_user)
):
    """Создает локальную комнату для 2 игроков на одном устройстве."""
    try:
        if not payload:
            try:
                payload = await request.json()
            except Exception:
                payload = {}

        if not isinstance(payload, dict):
            payload = {}

        game_type = str(payload.get("game_type") or "chess").strip().lower()
        host_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
        host_name = user.display_name if user else payload.get("host_name", "Белые")

        from backend.api.game_rooms import game_manager, chess
        if game_type == "chess" and chess is None:
            raise HTTPException(
                status_code=503,
                detail="Шахматный режим загружается на сервере. Пожалуйста, подождите минуту!"
            )

        room = game_manager.create_local_room(
            host_tg_id=host_tg_id,
            host_name=host_name,
            game_type=game_type
        )
        return room.to_dict(viewer_tg_id=host_tg_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_local_game: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")


@router.post("/games/invite")
async def invite_opponent_to_game(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Создает комнату и отправляет сообщение с вызовом сопернику в ЛС бота."""
    try:
        if not payload:
            try:
                payload = await request.json()
            except Exception:
                payload = {}

        if not isinstance(payload, dict):
            payload = {}

        game_type = str(payload.get("game_type") or "tictactoe").strip().lower()
        try:
            opponent_tg_id = int(payload.get("opponent_tg_id") or 0)
        except (ValueError, TypeError):
            opponent_tg_id = 0

        if not opponent_tg_id and game_type != "rpg_coop":
            raise HTTPException(status_code=400, detail="opponent_tg_id is required")

        if opponent_tg_id == 0:
            opponent_tg_id = None

        host_color = str(payload.get("host_color") or "white").strip().lower()
        host_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
        host_name = user.display_name if user else payload.get("host_name", "Одноклассник")

        from backend.api.game_rooms import game_manager, chess
        if game_type == "chess" and chess is None:
            raise HTTPException(
                status_code=503,
                detail="Шахматный режим загружается на сервере. Пожалуйста, подождите минуту или сыграйте в Крестики-нолики!"
            )

        opp_name = payload.get("opponent_name")
        if not opp_name:
            try:
                from backend.db.crud import get_user_by_tg_id
                opp_user = await get_user_by_tg_id(session, opponent_tg_id)
                opp_name = opp_user.display_name if opp_user else "Одноклассник"
            except Exception as ex:
                logger.warning(f"Could not get opponent user from DB: {ex}")
                opp_name = "Одноклассник"

        boss_id = str(payload.get("boss_id") or "golem").strip().lower()
        is_solo = bool(payload.get("is_solo", False))
        hero_data = payload.get("hero_data")
        if not hero_data and game_type in ["rpg_coop", "rpg_duel"]:
            from backend.api.routers.games_rpg_hooks import prepare_rpg_hero_data
            hero_data = await prepare_rpg_hero_data(session, user, host_name)

        room = game_manager.create_room(
            host_tg_id=host_tg_id,
            host_name=host_name,
            opponent_tg_id=opponent_tg_id,
            opponent_name=opp_name,
            game_type=game_type,
            host_color=host_color,
            boss_id=boss_id,
            is_solo=is_solo,
            hero_data=hero_data
        )

        from backend.bot.bot import get_current_bot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

        bot = get_current_bot()
        bot_notified = False
        if bot and opponent_tg_id:
            try:
                base_url = _get_public_webapp_url(request)
                separator = "&" if "?" in base_url else "?"
                escaped_host_name = html.escape(str(host_name or "Одноклассник"))

                if game_type in ["rpg_duel", "rpg_coop"]:
                    from backend.api.routers.games_rpg_hooks import get_rpg_invite_details
                    game_url, invite_text, btn_text = get_rpg_invite_details(
                        room, game_type, base_url, separator, opponent_tg_id, escaped_host_name
                    )
                elif game_type == "chess":
                    game_url = f"{base_url}{separator}room={room.room_id}&game=chess&tg_user_id={opponent_tg_id}"
                    host_color_actual = getattr(room, "host_color", "white")
                    if host_color_actual == "black":
                        color_line = "Твой цвет: <b>Белые ⚪</b> <i>(ходишь первым!)</i>"
                    else:
                        color_line = "Твой цвет: <b>Черные ⚫</b>"
                    if host_color == "random":
                        color_line += "\n<i>(Цвета определены случайным образом 🎲)</i>"

                    invite_text = (
                        f"♟️ <b>{escaped_host_name}</b> вызывает тебя на <b>Шахматную дуэль</b>!\n"
                        f"{color_line}\n\n"
                        f"⚡ Готов сыграть партию на перемене?"
                    )
                    btn_text = "♟️ Принять вызов и играть"
                else:
                    game_url = f"{base_url}{separator}room={room.room_id}&game=tictactoe&tg_user_id={opponent_tg_id}"
                    invite_text = (
                        f"🎮 <b>{escaped_host_name}</b> бросает тебе вызов в <b>Крестики-нолики</b>!\n\n"
                        f"⚡ Примешь бой на перемене?"
                    )
                    btn_text = "⚔️ Принять вызов и играть"

                if game_url.startswith("https://"):
                    play_btn = InlineKeyboardButton(
                        text=btn_text,
                        web_app=WebAppInfo(url=game_url)
                    )
                else:
                    play_btn = InlineKeyboardButton(
                        text=btn_text,
                        url=game_url
                    )

                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [play_btn],
                    [
                        InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=f"game_reject:{room.room_id}"
                        )
                    ]
                ])
                background_tasks.add_task(
                    _send_game_invite_notification,
                    bot,
                    opponent_tg_id,
                    invite_text,
                    kb
                )
                bot_notified = True
            except Exception as e:
                logger.warning(f"Error preparing invite notification: {e}")

        res = room.to_dict(viewer_tg_id=host_tg_id)
        res["bot_notified"] = bot_notified
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in invite_opponent_to_game: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")


@router.get("/games/room/{room_id}")
async def get_game_room_state(
    room_id: str,
    request: Request,
    tg_user_id: Optional[int] = Query(None),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Возвращает текущее состояние игровой комнаты."""
    from backend.api.game_rooms import game_manager
    room = game_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    viewer_tg_id = _extract_viewer_tg_id(user, request, query_tg_id=tg_user_id)
    if room and getattr(room, "game_type", None) == "rpg_coop" and room.status == "finished" and room.winner == "heroes":
        if not getattr(room, "reward_distributed", False):
            from backend.api.routers.games_rpg_hooks import handle_rpg_room_moved
            await handle_rpg_room_moved(room, session, user, viewer_tg_id)
    return room.to_dict(viewer_tg_id=viewer_tg_id)


@router.post("/games/room/{room_id}/join")
async def join_game_room(
    room_id: str,
    request: Request,
    payload: Dict[str, Any] = {},
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Подключение соперника к созданной комнате."""
    from backend.api.game_rooms import game_manager
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    user_name = user.display_name if user else payload.get("user_name", "Игрок")

    ok, msg = game_manager.join_room(room_id, viewer_tg_id, user_name)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    room = game_manager.get_room(room_id)
    if room:
        from backend.api.routers.games_rpg_hooks import handle_rpg_room_joined
        await handle_rpg_room_joined(room, session, user, user_name)
    return room.to_dict(viewer_tg_id=viewer_tg_id)


@router.post("/games/room/{room_id}/move")
async def make_game_move(
    room_id: str,
    request: Request,
    payload: Dict[str, Any],
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Ход в игре (Крестики-нолики, Шахматы или RPG)."""
    from backend.api.game_rooms import game_manager
    viewer_tg_id = _extract_viewer_tg_id(user, request, payload=payload) or 0
    move_val = payload.get("move") or payload.get("uci")
    if move_val is None:
        move_val = payload.get("cell")
    if move_val is None and "action" in payload:
        move_val = payload.get("action")

    ok, msg = game_manager.make_move(room_id, viewer_tg_id, move_val)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    room = game_manager.get_room(room_id)
    if room:
        from backend.api.routers.games_rpg_hooks import handle_rpg_room_moved
        await handle_rpg_room_moved(room, session, user, viewer_tg_id)
    return room.to_dict(viewer_tg_id=viewer_tg_id)



