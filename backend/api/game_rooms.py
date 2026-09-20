import time
import uuid
import logging
from typing import Dict, Optional, List, Any

from backend.api.rooms_tictactoe import WIN_COMBOS, TicTacToeRoom
from backend.api.rooms_chess import ChessRoom, chess
from backend.api.rpg_bosses import RAID_BOSSES
from backend.api.rpg_pvp import RPGPvPRoom
from backend.api.rpg_coop import RPGCoopBossRoom

logger = logging.getLogger(__name__)

__all__ = [
    "WIN_COMBOS", "TicTacToeRoom", "ChessRoom", "chess",
    "RAID_BOSSES", "RPGPvPRoom", "RPGCoopBossRoom",
    "GameRoomManager", "game_manager"
]

class GameRoomManager:
    def __init__(self):
        self.rooms: Dict[str, Any] = {}

    def cleanup(self):
        now = time.time()
        expired = [rid for rid, r in self.rooms.items() if now - r.last_activity > 7200]
        for rid in expired:
            del self.rooms[rid]

    def create_local_room(
        self,
        host_tg_id: int,
        host_name: str,
        game_type: str = "chess"
    ) -> Any:
        self.cleanup()
        room_id = "local_" + uuid.uuid4().hex[:8]
        if game_type == "chess":
            room = ChessRoom(
                room_id=room_id,
                host_tg_id=host_tg_id,
                host_name=host_name or "Белые",
                opponent_tg_id=host_tg_id,
                opponent_name="Черные",
                host_color="white",
                is_local=True
            )
            self.rooms[room_id] = room
            return room
        raise ValueError(f"Локальный режим не поддерживается для {game_type}")

    def create_room(
        self,
        host_tg_id: int,
        host_name: str,
        opponent_tg_id: Optional[int] = None,
        opponent_name: Optional[str] = None,
        game_type: str = "tictactoe",
        host_color: str = "white",
        boss_id: str = "roshan",
        is_solo: bool = False,
        hero_data: Optional[Dict[str, Any]] = None
    ) -> Any:
        self.cleanup()
        room_id = uuid.uuid4().hex[:10]
        if game_type == "chess":
            room = ChessRoom(
                room_id=room_id,
                host_tg_id=host_tg_id,
                host_name=host_name,
                opponent_tg_id=opponent_tg_id,
                opponent_name=opponent_name,
                host_color=host_color
            )
        elif game_type == "rpg_duel":
            from backend.api.rpg_pvp import RPGPvPRoom
            room = RPGPvPRoom(
                room_id=room_id,
                host_tg_id=host_tg_id,
                host_name=host_name,
                opponent_tg_id=opponent_tg_id,
                opponent_name=opponent_name,
                hero_data=hero_data
            )
        elif game_type == "rpg_coop":
            from backend.api.rpg_coop import RPGCoopBossRoom
            room = RPGCoopBossRoom(
                room_id=room_id,
                host_tg_id=host_tg_id,
                host_name=host_name,
                opponent_tg_id=opponent_tg_id,
                opponent_name=opponent_name,
                boss_id=boss_id,
                is_solo=is_solo,
                hero_data=hero_data
            )
        else:
            room = TicTacToeRoom(
                room_id=room_id,
                host_tg_id=host_tg_id,
                host_name=host_name,
                opponent_tg_id=opponent_tg_id,
                opponent_name=opponent_name
            )
        self.rooms[room_id] = room
        return room

    def get_room(self, room_id: str) -> Optional[Any]:
        return self.rooms.get(room_id)

    def join_room(self, room_id: str, user_tg_id: int, user_name: str) -> tuple[bool, str]:
        room = self.get_room(room_id)
        if not room:
            return False, "Комната не найдена"

        if room.status in ["canceled", "rejected"]:
            return False, f"Игра была отменена ({room.status})"

        if user_tg_id == room.host_tg_id:
            return True, "Вы создатель комнаты"

        if hasattr(room, "add_coop_player"):
            return room.add_coop_player(user_tg_id, user_name)

        if room.opponent_tg_id and room.opponent_tg_id != user_tg_id:
            return False, "Эта игра предназначена для другого игрока"

        # Opponent joins
        if hasattr(room, "set_opponent"):
            room.set_opponent(user_tg_id, user_name)
        else:
            room.opponent_tg_id = user_tg_id
            if user_name:
                room.opponent_name = user_name

        if room.status == "waiting":
            room.status = "playing"
        room.last_activity = time.time()
        return True, "Успешное подключение"

    def add_bot_to_coop(self, room_id: str) -> tuple[bool, str]:
        room = self.get_room(room_id)
        if not room or getattr(room, "game_type", None) != "rpg_coop":
            return False, "Комната рейда не найдена"
        if hasattr(room, "add_bot_ally"):
            return room.add_bot_ally()
        return False, "Не поддерживается"

    def make_move(self, room_id: str, user_tg_id: int, move_data: Any) -> tuple[bool, str]:
        room = self.get_room(room_id)
        if not room:
            return False, "Комната не найдена"
        return room.make_move(user_tg_id, move_data)

    def resign_room(self, room_id: str, user_tg_id: int) -> tuple[bool, str]:
        room = self.get_room(room_id)
        if not room:
            return False, "Комната не найдена"
        if hasattr(room, "resign"):
            return room.resign(user_tg_id)
        return False, "Сдача не поддерживается в этой игре"

    def request_rematch(self, room_id: str, user_tg_id: int) -> tuple[bool, str]:
        room = self.get_room(room_id)
        if not room:
            return False, "Комната не найдена"
        return room.request_rematch(user_tg_id)

    def reject_room(self, room_id: str, user_tg_id: int) -> bool:
        room = self.get_room(room_id)
        if not room:
            return False
        if room.opponent_tg_id and room.opponent_tg_id != user_tg_id:
            return False
        room.status = "rejected"
        room.last_activity = time.time()
        return True

    def cancel_room(self, room_id: str, user_tg_id: int) -> bool:
        room = self.get_room(room_id)
        if not room:
            return False
        if room.host_tg_id != user_tg_id:
            return False
        room.status = "canceled"
        room.last_activity = time.time()
        return True


# Global game room manager instance
game_manager = GameRoomManager()
