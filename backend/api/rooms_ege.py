"""Server-authoritative state for asynchronous EGE knowledge duels."""
import secrets
import time
from typing import Any, Optional


VOWELS = "аеёиоуыэюя"
# The server owns both prompt and answer: a browser cannot award itself a point.
STRESS_WORDS = (
    "алфавИт", "бАнты", "баловАть", "бухгАлтеров", "вероисповЕдание",
    "газопровОд", "диспансЕр", "договорЁнность", "докумЕнт", "жалюзИ",
    "знАчимость", "каталОг", "квартАл", "красивЕе", "кухОнный",
    "мЕстностей", "намЕрение", "нАчавший", "облегчИть", "отдАвший",
    "партЕр", "плодоносИть", "принЯвший", "свЁкла", "созЫв",
    "срЕдства", "тортЫ", "углубИть", "цемЕнт", "шАрфы",
)
VOCABULARY_WORDS = (
    "абитуриент", "абонемент", "аккомпанемент", "апелляция", "аппетит",
    "архитектор", "бассейн", "бюллетень", "велосипед", "винегрет",
    "воображение", "впечатление", "галерея", "гармония", "гипотеза",
    "декларация", "деликатес", "дирижёр", "дисциплина", "интеллигент",
    "инициатива", "каникулы", "коллекция", "компетентный", "конференция",
    "лаборатория", "мероприятие", "механизм", "ориентация", "панорама",
    "параграф", "привилегия", "прецедент", "реставрация", "сувенир",
    "территория", "университет", "фестиваль", "характер", "цивилизация",
    "эксперимент", "электроника", "энциклопедия", "эстакада",
)


class EGEDuelRoom:
    """A 10-question duel, with server-checked answers and sudden death."""

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
        self.questions: dict[int, Optional[dict]] = {}
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

    def _new_question(self) -> dict:
        if self.game_type == "ege_vocabulary_duel":
            word = secrets.choice(VOCABULARY_WORDS)
            return {"id": secrets.token_hex(8), "mode": "vocabulary", "word": word,
                    "masked": "".join("_" if char.lower() in VOWELS else char for char in word),
                    "answer": word}
        source = secrets.choice(STRESS_WORDS)
        target = next(index for index, char in enumerate(source) if char in VOWELS.upper())
        display = source.lower()
        return {"id": secrets.token_hex(8), "mode": "stress", "word": display,
                "vowel_indexes": [index for index, char in enumerate(display) if char in VOWELS],
                "answer": target}

    def _current_question(self, user_tg_id: int) -> Optional[dict]:
        if len(self.answers.get(user_tg_id, [])) >= self.round_size:
            return None
        if not self.questions.get(user_tg_id):
            self.questions[user_tg_id] = self._new_question()
        return self.questions[user_tg_id]

    def question_for(self, user_tg_id: int) -> Optional[dict]:
        """Return prompt data only; expected answers never leave the server."""
        question = self._current_question(user_tg_id)
        if not question:
            return None
        return {key: value for key, value in question.items() if key != "answer"}

    @staticmethod
    def _normalize_word(value: Any) -> str:
        return str(value or "").strip().lower().replace("ё", "е")

    def _is_correct(self, question: dict, submitted: Any) -> bool:
        if question["mode"] == "vocabulary":
            return self._normalize_word(submitted) == self._normalize_word(question["answer"])
        return isinstance(submitted, int) and submitted == question["answer"]

    def make_move(self, user_tg_id: int, move_data: Any) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "playing" or not self._is_member(user_tg_id):
            return False, "Дуэль сейчас недоступна"
        if not isinstance(move_data, dict) or "answer" not in move_data:
            return False, "Нужен ответ на вопрос"
        answers = self.answers.setdefault(user_tg_id, [])
        if len(answers) >= self.round_size:
            return False, "Сначала дождитесь соперника"
        question = self._current_question(user_tg_id)
        if not question:
            return False, "Вопрос недоступен"
        answers.append(self._is_correct(question, move_data["answer"]))
        self.questions[user_tg_id] = None
        if not self._both_finished():
            return True, "Ответ принят"
        host_errors = self._errors(self.host_tg_id)
        opponent_errors = self._errors(self.opponent_tg_id)
        # Sudden death is a reward for two flawless regular rounds only.
        # Equal mistakes end in a draw; random clicking must never open it.
        if self.sudden_round == 0 and host_errors == 0 and opponent_errors == 0:
            self.sudden_round = 1
            self.round_size += 1
            return True, "Оба без ошибок — внезапная смерть"
        if host_errors == opponent_errors:
            if self.sudden_round and host_errors == 0:
                self.sudden_round += 1
                self.round_size += 1
                return True, "Оба ответили верно — продолжаем внезапную смерть"
            self.status = "finished"
            self.winner = None
            return True, "Ничья — оба допустили одинаковое число ошибок"
        self.winner = self.host_tg_id if host_errors < opponent_errors else self.opponent_tg_id
        self.status = "finished"
        return True, "Дуэль завершена"

    def request_rematch(self, user_tg_id: int) -> tuple[bool, str]:
        if self.status != "finished" or not self._is_member(user_tg_id):
            return False, "Реванш пока недоступен"
        if self.rematch_requested_by and self.rematch_requested_by != user_tg_id:
            self.status, self.winner, self.sudden_round, self.round_size = "playing", None, 0, 10
            self.answers = {self.host_tg_id: [], self.opponent_tg_id: []}
            self.questions = {}
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
            "question": self.question_for(viewer_tg_id) if self.status == "playing" and viewer_tg_id else None,
        }
