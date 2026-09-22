import random
import time
import logging
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)

try:
    import chess
    from backend.api.chess_ai import get_best_bot_move, get_position_key
except ImportError:
    chess = None
    get_best_bot_move = None
    get_position_key = None
    logger.warning("Module 'chess' is not installed. Chess games will be unavailable until installed.")


class ChessRoom:
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
        self.game_type = "chess"
        self.host_tg_id = host_tg_id
        self.host_name = host_name
        self.opponent_tg_id = opponent_tg_id
        self.is_local = is_local
        self.is_bot = is_bot

        # Randomize host color if requested
        if host_color == "random":
            actual_color = random.choice(["white", "black"])
            self.color_choice_mode = "random"
        else:
            actual_color = host_color if host_color in ["white", "black"] else "white"
            self.color_choice_mode = actual_color

        self.host_color = actual_color
        self.bot_color = bot_color or ("black" if self.host_color == "white" else "white")
        self.opponent_name = opponent_name or ("🤖 Шахматный Бот (ИИ)" if is_bot else "Соперник")

        if self.host_color == "white":
            self.white_tg_id = host_tg_id
            self.white_name = host_name
            self.black_tg_id = opponent_tg_id
            self.black_name = self.opponent_name
        else:
            self.black_tg_id = host_tg_id
            self.black_name = host_name
            self.white_tg_id = opponent_tg_id
            self.white_name = self.opponent_name

        if chess is None:
            raise RuntimeError("Библиотека шахмат chess не установлена на сервере. Обратитесь к администратору.")

        self.board = chess.Board()
        self.status = "playing" if (is_local or is_bot) else "waiting"
        self.winner: Optional[str] = None  # "white", "black", "draw", or None
        self.termination_reason: Optional[str] = None  # "checkmate", "stalemate", "resignation", etc.
        self.rematch_requested_by: Optional[str] = None  # "white", "black", or None

        self.created_at = time.time()
        self.last_activity = time.time()
        self.position_history: List[str] = [get_position_key(self.board)] if get_position_key else []

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
        return "white" if self.board.turn == chess.WHITE else "black"

    @property
    def last_move(self) -> Optional[str]:
        return self.board.peek().uci() if len(self.board.move_stack) > 0 else None

    def _check_outcome(self):
        if self.board.is_checkmate():
            self.status, self.winner, self.termination_reason = "finished", ("white" if self.board.turn == chess.BLACK else "black"), "checkmate"
        elif self.board.is_stalemate():
            self.status, self.winner, self.termination_reason = "finished", "draw", "stalemate"
        elif self.board.is_insufficient_material():
            self.status, self.winner, self.termination_reason = "finished", "draw", "insufficient_material"
        elif self.board.can_claim_threefold_repetition():
            self.status, self.winner, self.termination_reason = "finished", "draw", "repetition"
        elif self.board.can_claim_fifty_moves():
            self.status, self.winner, self.termination_reason = "finished", "draw", "fifty_moves"

    def _make_bot_move(self):
        if not getattr(self, "is_bot", False) or self.status != "playing":
            return
        bot_c = chess.WHITE if self.bot_color == "white" else chess.BLACK
        if self.board.turn != bot_c or not get_best_bot_move:
            return
        move = get_best_bot_move(
            self.board,
            depth=3,
            bot_color=bot_c,
            position_history=self.position_history
        )
        if move and move in self.board.legal_moves:
            self.board.push(move)
            if get_position_key:
                self.position_history.append(get_position_key(self.board))
            self._check_outcome()

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

        uci_str = str(move_data).strip().lower()
        try:
            move = chess.Move.from_uci(uci_str)
        except Exception:
            return False, f"Некорректный формат хода: {uci_str}"

        if move not in self.board.legal_moves:
            # Check if auto-promotion to queen works
            if len(uci_str) == 4:
                try_promo = chess.Move.from_uci(uci_str + "q")
                if try_promo in self.board.legal_moves:
                    move = try_promo
                else:
                    return False, "Недопустимый ход по правилам шахмат"
            else:
                return False, "Недопустимый ход по правилам шахмат"

        self.board.push(move)
        if get_position_key:
            self.position_history.append(get_position_key(self.board))
        self._check_outcome()

        # If playing against bot, bot responds immediately
        if getattr(self, "is_bot", False) and self.status == "playing":
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
            self.position_history = [get_position_key(self.board)] if get_position_key else []
            self.winner = None
            self.termination_reason = None
            self.rematch_requested_by = None
            self.status = "playing"
            return True, "Новая игра начата"

        if getattr(self, "is_bot", False):
            self.host_color = "black" if self.host_color == "white" else "white"
            self.bot_color = "black" if self.host_color == "white" else "white"
            if self.host_color == "white":
                self.white_name = self.host_name
                self.black_name = self.opponent_name
            else:
                self.black_name = self.host_name
                self.white_name = self.opponent_name
            self.board.reset()
            self.position_history = [get_position_key(self.board)] if get_position_key else []
            self.winner = None
            self.termination_reason = None
            self.rematch_requested_by = None
            self.status = "playing"
            if self.bot_color == "white":
                self._make_bot_move()
            return True, "Новая игра с ботом начата со сменой цветов"

        role = self.get_player_role(user_tg_id)
        if not role:
            return False, "Вы не участник этой игры"

        other_role = "black" if role == "white" else "white"
        if self.rematch_requested_by == other_role:
            self.white_tg_id, self.black_tg_id = self.black_tg_id, self.white_tg_id
            self.white_name, self.black_name = self.black_name, self.white_name
            self.host_color = "black" if self.host_color == "white" else "white"

            self.board.reset()
            self.position_history = [get_position_key(self.board)] if get_position_key else []
            self.winner = None
            self.termination_reason = None
            self.rematch_requested_by = None
            self.status = "playing"
            return True, "Реванш начат со сменой цветов"
        else:
            self.rematch_requested_by = role
            return True, "Запрос на реванш отправлен"

    def get_captured_pieces(self) -> dict:
        initial = {
            "white": {"P": 8, "N": 2, "B": 2, "R": 2, "Q": 1},
            "black": {"p": 8, "n": 2, "b": 2, "r": 2, "q": 1}
        }
        current_counts: Dict[str, int] = {}
        for piece in self.board.piece_map().values():
            sym = piece.symbol()
            current_counts[sym] = current_counts.get(sym, 0) + 1

        captured_by_white = []
        for sym, count in initial["black"].items():
            diff = count - current_counts.get(sym, 0)
            if diff > 0:
                captured_by_white.extend([sym] * diff)

        captured_by_black = []
        for sym, count in initial["white"].items():
            diff = count - current_counts.get(sym, 0)
            if diff > 0:
                captured_by_black.extend([sym] * diff)

        return {
            "by_white": captured_by_white,
            "by_black": captured_by_black
        }

    def to_dict(self, viewer_tg_id: Optional[int] = None) -> dict:
        is_local = getattr(self, "is_local", False)
        is_bot = getattr(self, "is_bot", False)
        bot_color = getattr(self, "bot_color", None)
        viewer_role = self.turn if is_local else (self.host_color if is_bot else (self.get_player_role(viewer_tg_id) if viewer_tg_id else None))
        last_move = self.board.peek().uci() if len(self.board.move_stack) > 0 else None
        legal_moves = [m.uci() for m in self.board.legal_moves] if self.status == "playing" else []

        host_role = "white" if is_local else (self.host_color if is_bot else self.get_player_role(self.host_tg_id))
        opp_role = "black" if is_local else (bot_color if is_bot else (self.get_player_role(self.opponent_tg_id) if self.opponent_tg_id else None))

        return {
            "room_id": self.room_id,
            "game_type": "chess",
            "is_local": is_local,
            "is_bot": is_bot,
            "bot_color": bot_color,
            "status": self.status,
            "host_color": self.host_color,
            "color_choice_mode": getattr(self, "color_choice_mode", self.host_color),
            "host": {
                "tg_id": self.host_tg_id,
                "name": self.host_name,
                "role": host_role
            },
            "opponent": {
                "tg_id": self.opponent_tg_id,
                "name": self.opponent_name,
                "role": opp_role
            } if (self.opponent_tg_id or is_bot) else None,
            "white": {
                "tg_id": self.white_tg_id,
                "name": self.white_name
            },
            "black": {
                "tg_id": self.black_tg_id,
                "name": self.black_name
            } if (self.black_tg_id or is_bot) else None,
            "fen": self.board.fen(),
            "turn": self.turn,
            "winner": self.winner,
            "termination_reason": self.termination_reason,
            "rematch_requested_by": self.rematch_requested_by,
            "your_role": viewer_role,
            "is_your_turn": (self.status == "playing") if is_local else (self.status == "playing" and self.turn == viewer_role),
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "last_move": last_move,
            "legal_moves": legal_moves,
            "captured_pieces": self.get_captured_pieces()
        }
