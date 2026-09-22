"""Server state for asynchronous EGE knowledge duels."""
import time
from typing import Any, Optional


class EGEDuelRoom:
    """A 10-question duel followed by sudden death when both are perfect."""

    def __init__(self, room_id: str, host_tg_id: int, host_name: str,
                 opponent_tg_id: Optional[int] = None,
                 opponent_name: Optional[str] = None, game_type: str = "ege_stress_duel"):
        self.room_id = room_id
        self.game_type = game_type
        self.host_tg_id = host_tg_id
        self.host_name = host_name
        self.opponent_tg_id = opponent_tg_id
        self.opponent_name = opponent_name or "Соперник"
        self.status = "waiting"
        self.round_size = 10
        self.answers = {host_tg_id: []}
        if opponent_tg_id:
            self.answers[opponent_tg_id] = []
        self.sudden_round = 0
        self.winner: Optional[int] = None
        self.rematch_requested_by: Optional[int] = None
        self.created_at = self.last_activity = time.time()

    def set_opponent(self, user_tg_id: int, user_name: Optional[str] = None):
        self.opponent_tg_id = user_tg_id
        self.opponent_name = user_name or self.opponent_name
        self.answers.setdefault(user_tg_id, [])

    def _is_member(self, user_id: int) -> bool:
        return user_id in (self.host_tg_id, self.opponent_tg_id)

    def _errors(self, user_id: int) -> int:
        return sum(not answer for answer in self.answers.get(user_id, []))

    def _both_finished(self) -> bool:
        return self.opponent_tg_id is not None and all(
            len(self.answers.get(user_id, [])) >= self.round_size
            for user_id in (self.host_tg_id, self.opponent_tg_id)
        )

    def make_move(self, user_tg_id: int, move_data: Any) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "playing" or not self._is_member(user_tg_id):
            return False, "Дуэль сейчас недоступна"
        if not isinstance(move_data, dict) or not isinstance(move_data.get("correct"), bool):
            return False, "Нужен результат ответа"
        answers = self.answers.setdefault(user_tg_id, [])
        if len(answers) >= self.round_size:
            return False, "Сначала дождитесь соперника"
        answers.append(move_data["correct"])
        if not self._both_finished():
            return True, "Ответ принят"
        host_errors = self._errors(self.host_tg_id)
        opponent_errors = self._errors(self.opponent_tg_id)
        if self.sudden_round == 0 and host_errors == 0 and opponent_errors == 0:
            self.sudden_round = 1
            self.round_size += 1
            return True, "Оба без ошибок — внезапная смерть"
        if host_errors == opponent_errors:
            self.sudden_round += 1
            self.round_size += 1
            return True, "Ничья в раунде — продолжаем"
        self.winner = self.host_tg_id if host_errors < opponent_errors else self.opponent_tg_id
        self.status = "finished"
        return True, "Дуэль завершена"

    def request_rematch(self, user_tg_id: int) -> tuple[bool, str]:
        if self.status != "finished" or not self._is_member(user_tg_id):
            return False, "Реванш пока недоступен"
        if self.rematch_requested_by and self.rematch_requested_by != user_tg_id:
            self.status, self.winner, self.sudden_round, self.round_size = "playing", None, 0, 10
            self.answers = {self.host_tg_id: [], self.opponent_tg_id: []}
            self.rematch_requested_by = None
            return True, "Реванш начат"
        self.rematch_requested_by = user_tg_id
        return True, "Запрос на реванш отправлен"

    def to_dict(self, viewer_tg_id: Optional[int] = None) -> dict:
        ids = (self.host_tg_id, self.opponent_tg_id)
        return {
            "room_id": self.room_id, "game_type": self.game_type, "status": self.status,
            "host": {"tg_id": self.host_tg_id, "name": self.host_name},
            "opponent": {"tg_id": self.opponent_tg_id, "name": self.opponent_name} if self.opponent_tg_id else None,
            "your_answers": len(self.answers.get(viewer_tg_id, [])),
            "opponent_answers": len(self.answers.get(next((uid for uid in ids if uid and uid != viewer_tg_id), 0), [])),
            "your_errors": self._errors(viewer_tg_id) if viewer_tg_id in self.answers else 0,
            "round_size": self.round_size, "sudden_round": self.sudden_round,
            "winner": self.winner, "rematch_requested_by": self.rematch_requested_by,
        }
