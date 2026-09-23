# backend/api/rooms_checkers/room.py
"""Комната для игры в Русские шашки (онлайн, локально 2 на 1 телефоне и против бота)."""
import time
import random
import logging
from typing import Optional, Dict, Any
from backend.api.rooms_checkers.engine import CheckersBoard
from backend.api.rooms_checkers.ai import get_best_checkers_move

logger = logging.getLogger(__name__)


class CheckersRoom:
    def __init__(
        self,
        room_id: str,
        host_tg_id: int,
        host_name: str,
        opponent_tg_id: Optional[int] = None,
        opponent_name: Optional[str] = None,
        host_color: str = "white",
        is_local: bool = False,
        is_bot: bool = False,
        bot_color: Optional[str] = None
    ):
        self.room_id = room_id
        self.game_type = "checkers"
        self.host_tg_id = host_tg_id
        self.host_name = host_name
        self.opponent_tg_id = opponent_tg_id
        self.is_local = is_local
        self.is_bot = is_bot

        if host_color == "random":
            self.host_color = random.choice(["white", "black"])
            self.color_choice_mode = "random"
        else:
            self.host_color = host_color if host_color in ["white", "black"] else "white"
            self.color_choice_mode = self.host_color

        self.bot_color = bot_color or ("black" if self.host_color == "white" else "white")
        self.opponent_name = opponent_name or ("🤖 Шашечный Бот (ИИ)" if is_bot else "Соперник")

        if self.host_color == "white":
            self.white_tg_id, self.white_name = host_tg_id, host_name
            self.black_tg_id = None if is_bot else opponent_tg_id
            self.black_name = self.opponent_name
        else:
            self.black_tg_id, self.black_name = host_tg_id, host_name
            self.white_tg_id = None if is_bot else opponent_tg_id
            self.white_name = self.opponent_name

        self.board = CheckersBoard()
        self.status = "playing" if (is_local or is_bot) else "waiting"
        self.winner: Optional[str] = None
        self.termination_reason: Optional[str] = None
        self.rematch_requested_by: Optional[str] = None
        self.invite_msg_id: Optional[int] = None
        self.invite_chat_id: Optional[int] = None
        self.created_at = time.time()
        self.last_activity = time.time()

        # If bot plays white, it makes the opening move immediately
        if self.is_bot and self.bot_color == "white":
            self._make_bot_move()

    def set_opponent(self, user_tg_id: int, user_name: Optional[str] = None):
        self.opponent_tg_id = user_tg_id
        if user_name:
            self.opponent_name = user_name
        if self.host_color == "white":
            self.black_tg_id = user_tg_id
            if user_name:
                self.black_name = user_name
        else:
            self.white_tg_id = user_tg_id
            if user_name:
                self.white_name = user_name

    def get_player_role(self, user_tg_id: int) -> Optional[str]:
        if getattr(self, "is_local", False):
            return self.turn
        if getattr(self, "is_bot", False):
            return self.host_color
        if self.white_tg_id and user_tg_id == self.white_tg_id:
            return "white"
        if self.black_tg_id and user_tg_id == self.black_tg_id:
            return "black"
        return None

    @property
    def turn(self) -> str:
        return self.board.turn

    def _make_bot_move(self):
        """Выполняет ход бота (включая цепочки взятий)."""
        if not getattr(self, "is_bot", False) or self.status != "playing":
            return
        if self.turn != self.bot_color:
            return

        while self.turn == self.bot_color and self.status == "playing":
            move = get_best_checkers_move(self.board, depth=3, bot_color=self.bot_color)
            if not move:
                break
            ok, res = self.board.push_move(move)
            if not ok:
                logger.warning(f"Checkers bot move {move} failed: {res}")
                break
            if self.board.is_game_over():
                self.status = "finished"
                self.winner = self.board.get_winner()
                self.termination_reason = "elimination_or_lock"
                break
            if res == "done":
                break

    def make_move(self, user_tg_id: int, move_data: Any) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "playing":
            return False, "Игра не активна"

        if not getattr(self, "is_local", False):
            role = self.get_player_role(user_tg_id)
            if not role:
                return False, "Вы не участник этой игры"
            if self.turn != role:
                return False, "Сейчас ход другого игрока"

        ok, msg = self.board.push_move(str(move_data))
        if not ok:
            return False, msg

        if self.board.is_game_over():
            self.status = "finished"
            self.winner = self.board.get_winner()
            self.termination_reason = "elimination_or_lock"
        elif getattr(self, "is_bot", False) and self.status == "playing" and self.turn == self.bot_color:
            self._make_bot_move()

        return True, "Успешно"

    def resign(self, user_tg_id: int) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "playing":
            return False, "Игра не активна"

        if getattr(self, "is_local", False):
            role = self.turn
            self.status = "finished"
            self.winner = "black" if role == "white" else "white"
            self.termination_reason = "resignation"
            return True, "Сдача принята"

        if getattr(self, "is_bot", False):
            self.status = "finished"
            self.winner = self.bot_color
            self.termination_reason = "resignation"
            return True, "Сдача принята"

        role = self.get_player_role(user_tg_id)
        if not role:
            return False, "Вы не участник этой игры"

        self.status = "finished"
        self.winner = "black" if role == "white" else "white"
        self.termination_reason = "resignation"
        return True, "Сдача принята"

    def request_rematch(self, user_tg_id: int) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "finished":
            return False, "Игра еще не окончена"

        if getattr(self, "is_local", False):
            self.board.reset()
            self.winner = None
            self.termination_reason = None
            self.rematch_requested_by = None
            self.status = "playing"
            return True, "Новая игра начата"

        if getattr(self, "is_bot", False):
            self.host_color = "black" if self.host_color == "white" else "white"
            self.bot_color = "white" if self.host_color == "black" else "black"
            if self.host_color == "white":
                self.white_tg_id, self.white_name = self.host_tg_id, self.host_name
                self.black_tg_id, self.black_name = None, self.opponent_name
            else:
                self.black_tg_id, self.black_name = self.host_tg_id, self.host_name
                self.white_tg_id, self.white_name = None, self.opponent_name

            self.board.reset()
            self.winner = None
            self.termination_reason = None
            self.rematch_requested_by = None
            self.status = "playing"
            if self.bot_color == "white":
                self._make_bot_move()
            return True, "Реванш начат со сменой цветов"

        role = self.get_player_role(user_tg_id)
        if not role:
            return False, "Вы не участник этой игры"

        other_role = "black" if role == "white" else "white"
        if self.rematch_requested_by == other_role:
            self.white_tg_id, self.black_tg_id = self.black_tg_id, self.white_tg_id
            self.white_name, self.black_name = self.black_name, self.white_name
            self.host_color = "black" if self.host_color == "white" else "white"

            self.board.reset()
            self.winner = None
            self.termination_reason = None
            self.rematch_requested_by = None
            self.status = "playing"
            return True, "Реванш начат со сменой цветов"
        else:
            self.rematch_requested_by = role
            return True, "Запрос на реванш отправлен"

    def get_captured_pieces(self) -> dict:
        w_count, b_count = 0, 0
        for r in range(8):
            for c in range(8):
                p = self.board.board[r][c]
                if p in ('w', 'W'):
                    w_count += 1
                elif p in ('b', 'B'):
                    b_count += 1
        return {
            "by_white": ["b"] * max(0, 12 - b_count),
            "by_black": ["w"] * max(0, 12 - w_count)
        }

    def to_dict(self, viewer_tg_id: Optional[int] = None) -> dict:
        is_local = getattr(self, "is_local", False)
        is_bot = getattr(self, "is_bot", False)
        bot_color = getattr(self, "bot_color", "black")

        viewer_role = self.turn if is_local else (self.host_color if is_bot else (self.get_player_role(viewer_tg_id) if viewer_tg_id else None))
        last_move = self.board.move_history[-1] if self.board.move_history else None
        legal_moves = self.board.get_legal_moves() if self.status == "playing" else []

        host_role = "white" if is_local else (self.host_color if is_bot else self.get_player_role(self.host_tg_id))
        opp_role = "black" if is_local else (bot_color if is_bot else (self.get_player_role(self.opponent_tg_id) if self.opponent_tg_id else None))

        return {
            "room_id": self.room_id,
            "game_type": "checkers",
            "is_local": is_local,
            "is_bot": is_bot,
            "status": self.status,
            "host_color": self.host_color,
            "color_choice_mode": getattr(self, "color_choice_mode", self.host_color),
            "host": {"tg_id": self.host_tg_id, "name": self.host_name, "role": host_role},
            "opponent": {"tg_id": 0 if is_bot else self.opponent_tg_id, "name": self.opponent_name, "role": opp_role} if (self.opponent_tg_id or is_bot) else None,
            "white": {"tg_id": self.white_tg_id, "name": self.white_name} if (self.white_tg_id or (is_bot and self.bot_color == "white")) else None,
            "black": {"tg_id": self.black_tg_id, "name": self.black_name} if (self.black_tg_id or (is_bot and self.bot_color == "black")) else None,
            "fen": self.board.to_fen(),
            "turn": self.turn,
            "winner": self.winner,
            "termination_reason": self.termination_reason,
            "rematch_requested_by": self.rematch_requested_by,
            "your_role": viewer_role,
            "is_your_turn": (self.status == "playing") if is_local else (self.status == "playing" and self.turn == viewer_role),
            "last_move": last_move,
            "legal_moves": legal_moves,
            "active_jump_piece": self.board.active_jump_piece,
            "must_capture": self.board.has_captures(self.turn) if self.status == "playing" else False,
            "captured_pieces": self.get_captured_pieces()
        }
