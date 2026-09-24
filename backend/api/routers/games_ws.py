"""
WebSocket push-канал для игровых комнат.
Единый эндпоинт /ws/room/{room_id}/{user_id} обслуживает все типы комнат:
chess, checkers, tictactoe, ege-duel, rpg_duel, rpg_coop.

Как работает:
  1. Клиент открывает WS после получения room_id через HTTP.
  2. Сервер сразу шлёт полное состояние комнаты (type=state).
  3. Клиент держит соединение открытым, отправляя ping каждые 25 сек.
  4. После любого хода/join/action → broadcast_room() рассылает state всем.
  5. При обрыве — клиент плавно откатывается на HTTP-поллинг с ETag.
"""
import asyncio
import json
import logging
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

games_ws_router = APIRouter(tags=["games-ws"])


class GameRoomWsManager:
    """Реестр активных WS-соединений, сгруппированных по room_id."""

    def __init__(self) -> None:
        self._conns: Dict[str, List[WebSocket]] = {}

    # ── connection lifecycle ──────────────────────────────────────────────────

    async def connect(self, room_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._conns.setdefault(room_id, []).append(ws)
        logger.debug("[WS] connect room=%s total=%d", room_id, len(self._conns[room_id]))

    def disconnect(self, room_id: str, ws: WebSocket) -> None:
        bucket = self._conns.get(room_id, [])
        if ws in bucket:
            bucket.remove(ws)
        if not bucket:
            self._conns.pop(room_id, None)
        logger.debug("[WS] disconnect room=%s remaining=%d", room_id, len(bucket))

    def has_clients(self, room_id: str) -> bool:
        return bool(self._conns.get(room_id))

    # ── broadcast ─────────────────────────────────────────────────────────────

    async def broadcast_room(self, room_id: str, payload: dict) -> None:
        """Рассылает payload всем клиентам комнаты. Мёртвые соединения удаляются."""
        bucket = self._conns.get(room_id, [])
        if not bucket:
            return
        raw = json.dumps(payload, ensure_ascii=False, default=str)
        dead: List[WebSocket] = []
        for ws in list(bucket):
            try:
                await ws.send_text(raw)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)

    async def broadcast_raw(self, room_id: str, msg: str) -> None:
        bucket = self._conns.get(room_id, [])
        dead: List[WebSocket] = []
        for ws in list(bucket):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)


# Глобальный синглтон — импортируется из games.py, games_actions.py
room_ws_manager = GameRoomWsManager()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@games_ws_router.websocket("/ws/room/{room_id}/{user_id}")
async def room_ws_endpoint(websocket: WebSocket, room_id: str, user_id: int):
    """
    Клиент подключается сразу после получения room_id.
    Сервер шлёт full state на connect, затем push после каждого хода.
    Клиент может слать только `ping`; сервер отвечает `pong`.
    """
    from backend.api.game_rooms import game_manager
    from backend.api.ege_rating import build_ege_room_payload
    from backend.db.session import async_session_factory

    room = game_manager.get_room(room_id)
    if not room:
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "error", "message": "Room not found"}))
        await websocket.close(code=4004)
        return

    await room_ws_manager.connect(room_id, websocket)
    try:
        # Сразу шлём полное состояние
        async with async_session_factory() as session:
            payload = await build_ege_room_payload(session, room, user_id)
        await websocket.send_text(json.dumps({"type": "state", "payload": payload},
                                             ensure_ascii=False, default=str))
        # Heartbeat loop — клиент держит соединение живым
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # 60 сек тишины — шлём pong сами, чтобы Cloudflare не закрыл WS
                try:
                    await websocket.send_text("pong")
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("[WS] room=%s user=%d error: %s", room_id, user_id, e)
    finally:
        room_ws_manager.disconnect(room_id, websocket)
