import time
from typing import Optional, Any

WIN_COMBOS = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Cols
    (0, 4, 8), (2, 4, 6)              # Diags
]

class TicTacToeRoom:
    def __init__(
        self,
        room_id: str,
        host_tg_id: int,
        host_name: str,
        opponent_tg_id: Optional[int] = None,
        opponent_name: Optional[str] = None
    ):
        self.room_id = room_id
        self.game_type = "tictactoe"
        self.host_tg_id = host_tg_id
        self.host_name = host_name
        self.opponent_tg_id = opponent_tg_id
        self.opponent_name = opponent_name or "Соперник"
        
        # State: "waiting", "playing", "finished", "rejected", "canceled"
        self.status = "waiting"
        self.board = [""] * 9
        self.turn = "X"  # Host is X, opponent is O
        self.winner: Optional[str] = None  # "X", "O", "draw", or None
        self.rematch_requested_by: Optional[str] = None  # "X", "O", or None
        
        self.created_at = time.time()
        self.last_activity = time.time()

    def set_opponent(self, user_tg_id: int, user_name: Optional[str] = None):
        self.opponent_tg_id = user_tg_id
        self.o_tg_id = user_tg_id
        if user_name:
            self.opponent_name = user_name
            self.o_name = user_name

    def get_player_role(self, user_tg_id: int) -> Optional[str]:
        if user_tg_id == self.host_tg_id:
            return "X"
        if self.opponent_tg_id and user_tg_id == self.opponent_tg_id:
            return "O"
        return None

    def check_winner(self) -> Optional[str]:
        for a, b, c in WIN_COMBOS:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if all(cell != "" for cell in self.board):
            return "draw"
        return None

    def make_move(self, user_tg_id: int, cell_idx: Any) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "playing":
            return False, "Игра не активна"

        role = self.get_player_role(user_tg_id)
        if not role:
            return False, "Вы не участник этой игры"

        if self.turn != role:
            return False, "Сейчас ход другого игрока"

        try:
            c_idx = int(cell_idx)
        except Exception:
            return False, "Неверный индекс клетки"

        if not (0 <= c_idx < 9):
            return False, "Неверный индекс клетки"

        if self.board[c_idx] != "":
            return False, "Клетка уже занята"

        self.board[c_idx] = role
        win = self.check_winner()
        if win:
            self.status = "finished"
            self.winner = win
        else:
            self.turn = "O" if self.turn == "X" else "X"

        return True, "Успешно"

    def request_rematch(self, user_tg_id: int) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "finished":
            return False, "Игра еще не окончена"

        role = self.get_player_role(user_tg_id)
        if not role:
            return False, "Вы не участник этой игры"

        other_role = "O" if role == "X" else "X"
        if self.rematch_requested_by == other_role:
            # Both agreed to rematch! Reset board
            self.board = [""] * 9
            self.turn = "X"
            self.winner = None
            self.rematch_requested_by = None
            self.status = "playing"
            return True, "Реванш начат"
        else:
            self.rematch_requested_by = role
            return True, "Запрос на реванш отправлен"

    def to_dict(self, viewer_tg_id: Optional[int] = None) -> dict:
        viewer_role = self.get_player_role(viewer_tg_id) if viewer_tg_id else None
        return {
            "room_id": self.room_id,
            "game_type": "tictactoe",
            "status": self.status,
            "host": {
                "tg_id": self.host_tg_id,
                "name": self.host_name,
                "role": "X"
            },
            "opponent": {
                "tg_id": self.opponent_tg_id,
                "name": self.opponent_name,
                "role": "O"
            } if self.opponent_tg_id else None,
            "board": self.board,
            "turn": self.turn,
            "winner": self.winner,
            "rematch_requested_by": self.rematch_requested_by,
            "your_role": viewer_role,
            "is_your_turn": (self.status == "playing" and self.turn == viewer_role)
        }


