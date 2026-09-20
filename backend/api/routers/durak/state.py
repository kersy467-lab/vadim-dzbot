"""
Управление состоянием комнат и расчетом выигрышей/возвратов игры «Дурак».
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import HTTPException

from backend.db.session import async_session_factory
from backend.db.crud.users import add_user_coins
from backend.bot.game_durak import DurakGame

logger = logging.getLogger(__name__)

# Хранилище комнат в памяти:
# key: room_id, value: {"game": DurakGame|None, "mode": "bot"|"online", "players": [...], "stake": int, "settled": bool, "connections": {}}
_durak_rooms: Dict[str, dict] = {}


def _get_or_404(room_id: str) -> dict:
    room = _durak_rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    return room


def _durak_bot_auto_move(room_id: str) -> None:
    """Выполнить ходы за бота, пока ход не вернется игроку или игра не завершится."""
    room = _durak_rooms.get(room_id)
    if not room or not room.get("game"):
        return
    game = room["game"]
    for _ in range(20):
        if game.phase == "done":
            break
        if (game.phase == "attack" and game.current_attacker in game.bot_indices) or \
           (game.phase == "defend" and game.current_defender in game.bot_indices):
            mv = game.bot_move()
            if mv is None:
                break
        else:
            break


async def _durak_check_settlement(room_id: str) -> None:
    """Начислить выигрыш победителю или вернуть ставки при ничьей при окончании партии."""
    room = _durak_rooms.get(room_id)
    if not room or not room.get("game"):
        return
    game: DurakGame = room["game"]
    if game.phase != "done" or room.get("settled"):
        return

    room["settled"] = True
    stake = room.get("stake", 0)
    if stake <= 0:
        return

    mode = room.get("mode", "bot")
    async with async_session_factory() as session:
        if game.winner:
            if mode == "bot":
                # Победа человека над ботом: возвращается ставка + выигрыш (+ stake * 2)
                if game.winner > 0:
                    await add_user_coins(session, game.winner, stake * 2)
                    logger.info(f"Durak bot game settled: user {game.winner} won {stake * 2} coins!")
                else:
                    logger.info(f"Durak bot game settled: bot won, user lost {stake} coins.")
            else:
                # Онлайн мультиплеер: победитель забирает весь банк
                total_pot = stake * len(room["players"])
                if game.winner > 0:
                    await add_user_coins(session, game.winner, total_pot)
                    logger.info(f"Durak online room {room_id} settled: winner {game.winner} received {total_pot} coins!")
        else:
            # Ничья: возврат ставок всем игрокам
            for pid in room["players"]:
                if pid > 0:
                    await add_user_coins(session, pid, stake)
            logger.info(f"Durak room {room_id} ended in draw: refunded {stake} coins to players.")


async def _durak_broadcast(room_id: str, custom_payload: Optional[dict] = None) -> None:
    """Отправить обновление состояния или кастомное сообщение всем подключенным клиентам."""
    room = _durak_rooms.get(room_id)
    if not room:
        return
    connections = room.get("connections", {})
    dead = []

    for pid, ws in list(connections.items()):
        try:
            if custom_payload:
                await ws.send_text(json.dumps(custom_payload))
            elif room.get("game"):
                state = room["game"].to_state(for_player_id=pid)
                await ws.send_text(json.dumps({"type": "state", "state": state}))
            else:
                await ws.send_text(json.dumps({
                    "type": "waiting",
                    "players": room["players"],
                    "stake": room.get("stake", 0)
                }))
        except Exception:
            dead.append(pid)

    for pid in dead:
        connections.pop(pid, None)


async def _durak_leave_room(room_id: str, viewer_id: int) -> dict:
    """
    Выход из комнаты или отмена с гарантированным возвратом ставки:
    - В лобби ожидания: отмена создателем возвращает ставки всем; выход участника возвращает его ставку.
    - В игре с ботом: досрочный выход возвращает ставку игроку.
    - В онлайн-игре: досрочный выход засчитывается как сдача, банк переходит оставшемуся сопернику.
    """
    room = _durak_rooms.get(room_id)
    if not room:
        return {"ok": True, "status": "left", "message": "Комната уже закрыта"}

    stake = room.get("stake", 0)
    mode = room.get("mode", "bot")
    game = room.get("game")

    # 1. Лобби ожидания (игра ещё не началась)
    if game is None:
        players = room.get("players", [])
        is_creator = bool(players and viewer_id == players[0]) or len(players) <= 1

        if is_creator:
            # Создатель отменяет комнату: возврат ставок ВСЕМ игрокам
            if stake > 0:
                async with async_session_factory() as session:
                    for pid in players:
                        if pid > 0:
                            await add_user_coins(session, pid, stake)

            await _durak_broadcast(room_id, {
                "type": "canceled",
                "message": "Комната отменена создателем. Ставки возвращены."
            })
            _durak_rooms.pop(room_id, None)
            return {"ok": True, "status": "canceled", "refunded": stake > 0}
        else:
            # Участник выходит из комнаты: возврат ЕГО ставки
            if viewer_id in players:
                players.remove(viewer_id)
                if stake > 0:
                    async with async_session_factory() as session:
                        await add_user_coins(session, viewer_id, stake)

                # Оповестить оставшихся игроков в лобби
                await _durak_broadcast(room_id, {
                    "type": "waiting",
                    "players": players,
                    "stake": stake
                })
            return {"ok": True, "status": "left", "refunded": stake > 0}

    # 2. Игра с ботом
    if mode == "bot":
        # Если игра ещё не была рассчитана — возвращаем ставку игроку
        if stake > 0 and not room.get("settled"):
            async with async_session_factory() as session:
                await add_user_coins(session, viewer_id, stake)
            room["settled"] = True
        _durak_rooms.pop(room_id, None)
        return {"ok": True, "status": "left", "refunded": stake > 0}

    # 3. Онлайн игра уже идёт
    if not room.get("settled") and game.phase != "done":
        # Техническое поражение вышедшего игрока, победа соперника
        remaining = [p for p in room["players"] if p != viewer_id and p > 0]
        winner_id = remaining[0] if remaining else None
        if winner_id and stake > 0:
            total_pot = stake * len(room["players"])
            async with async_session_factory() as session:
                await add_user_coins(session, winner_id, total_pot)
                logger.info(f"Durak player {viewer_id} left room {room_id}. Awarded pot {total_pot} to {winner_id}")

        game.winner = winner_id
        game.loser = viewer_id
        game.phase = "done"
        room["settled"] = True

        await _durak_broadcast(room_id, {
            "type": "opponent_left",
            "winner": winner_id,
            "loser": viewer_id,
            "state": game.to_state()
        })

    _durak_rooms.pop(room_id, None)
    return {"ok": True, "status": "forfeited"}
