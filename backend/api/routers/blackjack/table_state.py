"""
Менеджер состояния и комнат многопользовательского стола «Блэкджек» (2–4 игрока).
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import WebSocket, WebSocketDisconnect

from backend.db.session import async_session_factory
from backend.db.crud.users import add_user_coins, get_user_by_tg_id
from backend.bot.game_blackjack import BlackjackTableGame

logger = logging.getLogger(__name__)

# Хранилище столов: table_id -> {"game": BlackjackTableGame, "connections": {}, "settled": bool, "creator_id": int}
_bj_tables: Dict[str, dict] = {}


def get_table(table_id: str) -> Optional[dict]:
    return _bj_tables.get(table_id)


def list_open_tables() -> List[dict]:
    res = []
    for tid, entry in _bj_tables.items():
        g: BlackjackTableGame = entry["game"]
        if g.phase in ("lobby", "betting") and len(g.players) < g.max_players:
            res.append({
                "table_id": tid,
                "players_count": len(g.players),
                "max_players": g.max_players,
                "min_stake": g.min_stake,
                "phase": g.phase,
            })
    return res


def create_table(creator_id: int, creator_name: str, max_players: int = 4, min_stake: int = 10) -> dict:
    game = BlackjackTableGame(max_players=max_players, min_stake=min_stake)
    game.add_player(creator_id, creator_name)
    entry = {
        "game": game,
        "connections": {},
        "settled": False,
        "creator_id": creator_id,
    }
    _bj_tables[game.table_id] = entry
    return entry


def join_table(table_id: str, user_id: int, user_name: str) -> Dict[str, Any]:
    entry = _bj_tables.get(table_id)
    if not entry:
        return {"ok": False, "error": "Стол не найден"}
    game: BlackjackTableGame = entry["game"]
    if game.phase not in ("lobby", "betting", "settled"):
        return {"ok": False, "error": "Раунд уже идёт, дождитесь окончания"}
    if len(game.players) >= game.max_players and not any(p.user_id == user_id for p in game.players):
        return {"ok": False, "error": "За столом нет свободных мест"}

    added = game.add_player(user_id, user_name)
    if not added:
        return {"ok": False, "error": "Не удалось занять место"}
    return {"ok": True, "state": game.to_dict()}


async def leave_table(table_id: str, user_id: int) -> Dict[str, Any]:
    entry = _bj_tables.get(table_id)
    if not entry:
        return {"ok": True}
    game: BlackjackTableGame = entry["game"]
    player = next((p for p in game.players if p.user_id == user_id), None)

    # Возврат ставки, если раунд ещё не начался (фаза ставок)
    if player and player.stake > 0 and game.phase in ("lobby", "betting") and not entry.get("settled"):
        async with async_session_factory() as session:
            await add_user_coins(session, user_id, player.stake)
        player.stake = 0

    game.remove_player(user_id)
    entry.get("connections", {}).pop(user_id, None)

    if not game.players:
        _bj_tables.pop(table_id, None)
    else:
        await broadcast_table(table_id)

    return {"ok": True}


async def place_table_bet(table_id: str, user_id: int, stake: int) -> Dict[str, Any]:
    entry = _bj_tables.get(table_id)
    if not entry:
        return {"ok": False, "error": "Стол не найден"}
    game: BlackjackTableGame = entry["game"]

    if stake < game.min_stake:
        return {"ok": False, "error": f"Минимальная ставка: {game.min_stake} 🪙"}

    # Проверка баланса и списание ставки
    async with async_session_factory() as session:
        db_user = await get_user_by_tg_id(session, user_id)
        if not db_user or (db_user.coins or 0) < stake:
            return {"ok": False, "error": f"Недостаточно монет. Ваш баланс: {getattr(db_user, 'coins', 0) or 0} 🪙"}
        await add_user_coins(session, user_id, -stake)

    res = game.place_bet(user_id, stake)
    if not res.get("ok"):
        # Возврат в случае ошибки
        async with async_session_factory() as session:
            await add_user_coins(session, user_id, stake)
        return res

    entry["settled"] = False
    await broadcast_table(table_id)
    return {"ok": True, "all_ready": res.get("all_ready", False)}


async def start_table_deal(table_id: str) -> Dict[str, Any]:
    entry = _bj_tables.get(table_id)
    if not entry:
        return {"ok": False, "error": "Стол не найден"}
    game: BlackjackTableGame = entry["game"]
    res = game.start_deal()
    if not res.get("ok"):
        return res

    # Проверка: если все закончили ход сразу (например, у всех Блэкджек)
    if game.phase == "settled":
        await check_table_settlement(table_id)

    await broadcast_table(table_id)
    return {"ok": True, "state": game.to_dict()}


async def player_table_action(table_id: str, user_id: int, action: str) -> Dict[str, Any]:
    entry = _bj_tables.get(table_id)
    if not entry:
        return {"ok": False, "error": "Стол не найден"}
    game: BlackjackTableGame = entry["game"]

    if action == "hit":
        res = game.player_hit(user_id)
    elif action == "stand":
        res = game.player_stand(user_id)
    elif action == "double":
        player = next((p for p in game.players if p.user_id == user_id), None)
        if player:
            extra = player.stake  # удвоение требует еще 1x ставки
            async with async_session_factory() as session:
                db_user = await get_user_by_tg_id(session, user_id)
                if not db_user or (db_user.coins or 0) < extra:
                    return {"ok": False, "error": f"Недостаточно монет для удвоения ({extra} 🪙)"}
                await add_user_coins(session, user_id, -extra)
        res = game.player_double(user_id)
    else:
        return {"ok": False, "error": f"Неизвестное действие: {action}"}

    if not res.get("ok"):
        return res

    if game.phase == "settled":
        await check_table_settlement(table_id)

    await broadcast_table(table_id)
    return {"ok": True, "state": game.to_dict()}


async def check_table_settlement(table_id: str) -> None:
    """Выплата выигрышей всем игрокам при завершении раунда."""
    entry = _bj_tables.get(table_id)
    if not entry or entry.get("settled"):
        return
    game: BlackjackTableGame = entry["game"]
    if game.phase != "settled":
        return

    entry["settled"] = True
    async with async_session_factory() as session:
        for p in game.players:
            if p.payout > 0:
                await add_user_coins(session, p.user_id, p.payout)
                logger.info(f"BJ Table {table_id}: credited {p.payout} coins to user {p.user_id} (status: {p.status})")


async def broadcast_table(table_id: str, custom_payload: Optional[dict] = None) -> None:
    entry = _bj_tables.get(table_id)
    if not entry:
        return
    conns = entry.get("connections", {})
    game: BlackjackTableGame = entry["game"]
    state_payload = custom_payload or {"type": "table_state", "state": game.to_dict()}
    msg_str = json.dumps(state_payload)

    dead = []
    for uid, ws in list(conns.items()):
        try:
            await ws.send_text(msg_str)
        except Exception:
            dead.append(uid)

    for uid in dead:
        conns.pop(uid, None)
