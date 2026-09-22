"""Server-authoritative state for EGE Arena duels."""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
from typing import Any, Optional

from backend.ege.words_stress import (
    STRESS_WORDS_FIPI as STRESS_WORDS,
    create_stress_question,
    pick_unique_stress_questions,
)
from backend.ege.words_vocabulary import (
    VOCABULARY_WORDS_FIPI as VOCABULARY_WORDS,
    create_vocab_question,
    pick_unique_vocab_questions,
)

logger = logging.getLogger(__name__)

VOWELS = "аеёиоуыэюя"


class EGEDuelRoom:
    """Fixed 10-question duel. Questions are unique and synchronized per duel."""

    def __init__(self, room_id: str, host_tg_id: int, host_name: str,
                 opponent_tg_id: Optional[int] = None,
                 opponent_name: Optional[str] = None, game_type: str = "ege_stress_duel"):
        self.room_id = room_id
        self.game_type = game_type
        self.host_tg_id = int(host_tg_id)
        self.host_name = host_name
        self.opponent_tg_id = int(opponent_tg_id) if opponent_tg_id else None
        self.opponent_name = opponent_name or "Соперник"
        self.status = "waiting"
        self.round_size = 10
        self.sudden_round = 0
        self.answers: dict[int, list[bool]] = {self.host_tg_id: []}
        if self.opponent_tg_id:
            self.answers[self.opponent_tg_id] = []
        self.questions: dict[int, Optional[dict]] = {}
        self.winner: Optional[int] = None
        self.finished_at: Optional[float] = None
        self.rematch_requested_by: Optional[int] = None
        self.rating_settled = False
        self.rating_changes: dict[int, int] = {}
        self.rating_snapshots: dict[int, dict[str, int]] = {}
        self.settlement_lock = asyncio.Lock()
        self.created_at = self.last_activity = time.time()

        self.deck: list[dict[str, Any]] = []
        self.used_words: set[str] = set()
        self._init_deck()

    def _init_deck(self) -> None:
        self.deck.clear()
        self.used_words.clear()
        self._ensure_deck_size(self.round_size)

    def _ensure_deck_size(self, target_size: int) -> None:
        needed = target_size - len(self.deck)
        if needed <= 0:
            return
        if self.game_type == "ege_vocabulary_duel":
            new_questions = pick_unique_vocab_questions(needed, exclude_words=self.used_words)
        else:
            new_questions = pick_unique_stress_questions(needed, exclude_words=self.used_words)
        for q in new_questions:
            self.deck.append(q)
            self.used_words.add(q["word"].lower())

    def set_opponent(self, user_tg_id: int, user_name: Optional[str] = None):
        self.opponent_tg_id = int(user_tg_id)
        self.opponent_name = user_name or self.opponent_name
        self.answers.setdefault(self.opponent_tg_id, [])

    def _is_member(self, user_id: int) -> bool:
        return int(user_id) in (self.host_tg_id, self.opponent_tg_id)

    def _errors(self, user_id: Optional[int]) -> int:
        if not user_id:
            return 0
        return sum(not answer for answer in self.answers.get(int(user_id), []))

    def _finished(self, user_id: Optional[int]) -> bool:
        return bool(user_id) and len(self.answers.get(int(user_id), [])) >= self.round_size

    def _both_finished(self) -> bool:
        return self._finished(self.host_tg_id) and self._finished(self.opponent_tg_id)

    def _new_question(self) -> dict:
        """Single question fallback generator."""
        if self.game_type == "ege_vocabulary_duel":
            qs = pick_unique_vocab_questions(1, exclude_words=self.used_words)
            return qs[0] if qs else create_vocab_question(secrets.choice(VOCABULARY_WORDS))
        qs = pick_unique_stress_questions(1, exclude_words=self.used_words)
        return qs[0] if qs else create_stress_question(secrets.choice(STRESS_WORDS))

    def _current_question(self, user_tg_id: int) -> Optional[dict]:
        uid = int(user_tg_id)
        if self._finished(uid):
            return None
        idx = len(self.answers.get(uid, []))
        self._ensure_deck_size(idx + 1)
        if idx < len(self.deck):
            q = self.deck[idx]
            self.questions[uid] = q
            return q
        return None

    def question_for(self, user_tg_id: int) -> Optional[dict]:
        question = self._current_question(user_tg_id)
        return {k: v for k, v in question.items() if k != "answer"} if question else None

    @staticmethod
    def _normalize_word(value: Any) -> str:
        text = str(value or "").strip().lower().replace("ё", "е")
        return re.sub(r"\s+", "", text)

    def _is_correct(self, question: dict, submitted: Any) -> bool:
        if question["mode"] == "vocabulary":
            return self._normalize_word(submitted) == self._normalize_word(question["answer"])
        try:
            return not isinstance(submitted, bool) and int(submitted) == int(question["answer"])
        except (ValueError, TypeError):
            return False

    def _finalize_if_ready(self) -> None:
        if not self._both_finished() or self.status == "finished":
            return
        host_errors = self._errors(self.host_tg_id)
        opponent_errors = self._errors(self.opponent_tg_id)
        if host_errors == opponent_errors:
            # Ничьей быть не должно: переходим к внезапной смерти (sudden death)
            self.sudden_round += 1
            self.round_size += 1
            self._ensure_deck_size(self.round_size)
            self.questions[self.host_tg_id] = None
            if self.opponent_tg_id:
                self.questions[self.opponent_tg_id] = None
            logger.info(
                "EGE duel entered sudden death room=%s type=%s sudden_round=%s round_size=%s errors=%s:%s",
                self.room_id, self.game_type, self.sudden_round, self.round_size, host_errors, opponent_errors,
            )
            return

        self.winner = self.host_tg_id if host_errors < opponent_errors else self.opponent_tg_id
        self.status = "finished"
        self.finished_at = time.time()
        logger.info(
            "EGE duel finalized room=%s type=%s winner=%s score=%s:%s errors=%s:%s sudden_rounds=%s",
            self.room_id, self.game_type, self.winner,
            self.round_size - host_errors, self.round_size - opponent_errors,
            host_errors, opponent_errors, self.sudden_round,
        )

    def make_move(self, user_tg_id: int, move_data: Any) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "playing" or not self._is_member(user_tg_id):
            return False, "Дуэль сейчас недоступна"
        if not isinstance(move_data, dict):
            if move_data is not None:
                move_data = {"answer": move_data}
            else:
                return False, "Нужен ответ на вопрос"
        elif "answer" not in move_data:
            return False, "Нужен ответ на вопрос"

        answers = self.answers.setdefault(int(user_tg_id), [])
        if len(answers) >= self.round_size:
            return False, "Вы уже закончили — дождитесь соперника"
        question = self._current_question(int(user_tg_id))
        if not question:
            return False, "Вопрос недоступен"
        answers.append(self._is_correct(question, move_data["answer"]))
        self.questions[int(user_tg_id)] = None
        if len(answers) == self.round_size:
            logger.info(
                "EGE duel player finished room=%s player=%s errors=%s waiting_for_opponent=%s",
                self.room_id, int(user_tg_id), self._errors(int(user_tg_id)), not self._both_finished(),
            )
        self._finalize_if_ready()
        if self.status == "finished":
            return True, "Дуэль завершена"
        if self.sudden_round > 0 and len(answers) < self.round_size:
            return True, "Внезапная смерть! Дополнительный раунд"
        if self._finished(user_tg_id):
            return True, "Результат сохранён — ждём соперника"
        return True, "Ответ принят"

    def request_rematch(self, user_tg_id: int) -> tuple[bool, str]:
        if self.status != "finished" or not self._is_member(user_tg_id):
            return False, "Реванш пока недоступен"
        if self.rematch_requested_by and self.rematch_requested_by != int(user_tg_id):
            self.status, self.winner, self.finished_at = "playing", None, None
            self.answers = {self.host_tg_id: [], int(self.opponent_tg_id): []}
            self.questions = {}
            self.rematch_requested_by = None
            self.rating_settled = False
            self.rating_changes = {}
            self.rating_snapshots = {}
            self.round_size = 10
            self.sudden_round = 0
            self._init_deck()
            return True, "Реванш начат"
        self.rematch_requested_by = int(user_tg_id)
        return True, "Запрос на реванш отправлен"

    def to_dict(self, viewer_tg_id: Optional[int] = None) -> dict:
        viewer = int(viewer_tg_id) if viewer_tg_id else None
        ids = (self.host_tg_id, self.opponent_tg_id)
        rival = next((uid for uid in ids if uid and uid != viewer), None)
        your_answers, rival_answers = len(self.answers.get(viewer, [])), len(self.answers.get(rival, []))
        your_errors, rival_errors = self._errors(viewer), self._errors(rival)
        winner_name = self.host_name if self.winner == self.host_tg_id else (
            self.opponent_name if self.winner == self.opponent_tg_id else None
        )
        result = None
        if self.status == "finished" and viewer:
            result = "draw" if self.winner is None else ("win" if self.winner == viewer else "loss")
        return {
            "room_id": self.room_id, "game_type": self.game_type, "status": self.status,
            "host": {"tg_id": self.host_tg_id, "name": self.host_name},
            "opponent": {"tg_id": self.opponent_tg_id, "name": self.opponent_name} if self.opponent_tg_id else None,
            "your_answers": your_answers, "opponent_answers": rival_answers,
            "your_errors": your_errors, "opponent_errors": rival_errors,
            "your_score": your_answers - your_errors, "opponent_score": rival_answers - rival_errors,
            "your_finished": self._finished(viewer), "opponent_finished": self._finished(rival),
            "round_size": self.round_size,
            "sudden_round": self.sudden_round,
            "is_sudden_death": self.sudden_round > 0,
            "winner": self.winner, "winner_name": winner_name, "result": result,
            "rematch_requested_by": self.rematch_requested_by,
            "question": self.question_for(viewer) if self.status == "playing" and viewer else None,
        }
