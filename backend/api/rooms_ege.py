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
MAIN_ROUND_TIME_LIMIT = 35.0
VOCAB_ROUND_TIME_LIMIT = 70.0
SUDDEN_WORD_TIME_LIMIT = 5.0
VOCAB_SUDDEN_WORD_TIME_LIMIT = 12.0
GRACE_PERIOD = 1.0



class EGEDuelRoom:
    """Fixed 10-question duel. Questions are unique and synchronized per duel."""

    def __init__(self, room_id: str, host_tg_id: int, host_name: str,
                 opponent_tg_id: Optional[int] = None,
                 opponent_name: Optional[str] = None, game_type: str = "ege_stress_duel"):
        self.room_id, self.game_type = room_id, game_type
        self.host_tg_id, self.host_name = int(host_tg_id), host_name
        self.opponent_tg_id = int(opponent_tg_id) if opponent_tg_id else None
        self.opponent_name = opponent_name or "Соперник"
        self.matchmaking_search = False
        self.matchmaking_recipient_count = 0
        self.matchmaking_messages: list[tuple[int, int]] = []
        self.status, self.round_size, self.sudden_round = "waiting", 10, 0
        self.answers: dict[int, list[bool]] = {self.host_tg_id: []}
        if self.opponent_tg_id:
            self.answers[self.opponent_tg_id] = []
        self.questions: dict[int, Optional[dict]] = {}
        self.winner, self.finished_at, self.rematch_requested_by = None, None, None
        self.rating_settled, self.rating_changes, self.rating_snapshots = False, {}, {}
        self.results_notified = False
        self.settlement_lock = asyncio.Lock()
        self.created_at = self.last_activity = time.time()
        self.player_started_at: dict[int, float] = {}
        self.sudden_question_started_at: dict[tuple[int, int], float] = {}
        self.deck: list[dict[str, Any]] = []
        self.used_words: set[str] = set()
        self._init_deck()

    @property
    def main_round_limit(self) -> float:
        return VOCAB_ROUND_TIME_LIMIT if self.game_type == "ege_vocabulary_duel" else MAIN_ROUND_TIME_LIMIT

    @property
    def sudden_word_limit(self) -> float:
        return VOCAB_SUDDEN_WORD_TIME_LIMIT if self.game_type == "ege_vocabulary_duel" else SUDDEN_WORD_TIME_LIMIT

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
        self._ensure_timer_started(int(user_tg_id))
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

    def _ensure_timer_started(self, uid: int) -> None:
        if self.status != "playing" or not uid or not self._is_member(uid):
            return
        answers = self.answers.setdefault(int(uid), [])
        if len(answers) >= self.round_size:
            return
        now = time.time()
        if self.sudden_round == 0:
            if uid not in self.player_started_at:
                self.player_started_at[uid] = now
        else:
            key = (int(uid), self.sudden_round)
            if key not in self.sudden_question_started_at:
                self.sudden_question_started_at[key] = now

    def _finish_timeout_forfeit(self, uid: int) -> None:
        """Finish the duel immediately when a player runs out of answer time."""
        answers = self.answers.setdefault(uid, [])
        while len(answers) < self.round_size:
            answers.append(False)
        self.questions[uid] = None
        self.winner = self.opponent_tg_id if uid == self.host_tg_id else self.host_tg_id
        self.status = "finished"
        self.finished_at = time.time()
        logger.info(
            "EGE duel timeout forfeit room=%s player=%s winner=%s round=%s",
            self.room_id, uid, self.winner, self.sudden_round,
        )

    def _check_timeouts(self) -> None:
        if self.status != "playing":
            return
        now = time.time()
        timed_out: list[int] = []
        for uid in (self.host_tg_id, self.opponent_tg_id):
            if not uid:
                continue
            answers = self.answers.setdefault(uid, [])
            if len(answers) >= self.round_size:
                continue
            if self.sudden_round == 0:
                started = self.player_started_at.get(uid)
                if started and (now - started) >= (self.main_round_limit + GRACE_PERIOD):
                    while len(answers) < 10:
                        answers.append(False)
                    self.questions[uid] = None
                    timed_out.append(uid)
                    logger.info("EGE duel main round timeout room=%s player=%s", self.room_id, uid)
            else:
                key = (uid, self.sudden_round)
                started = self.sudden_question_started_at.get(key)
                if started and (now - started) >= (self.sudden_word_limit + GRACE_PERIOD):
                    answers.append(False)
                    self.questions[uid] = None
                    timed_out.append(uid)
                    logger.info("EGE duel sudden death timeout room=%s player=%s round=%s", self.room_id, uid, self.sudden_round)
        if len(timed_out) == 1:
            self._finish_timeout_forfeit(timed_out[0])
        else:
            self._finalize_if_ready()

    def get_time_remaining(self, uid: Optional[int]) -> float:
        if not uid or self.status != "playing":
            return 0.0
        uid = int(uid)
        answers = self.answers.get(uid, [])
        if len(answers) >= self.round_size:
            return 0.0
        now = time.time()
        if self.sudden_round == 0:
            started = self.player_started_at.get(uid)
            if not started:
                return self.main_round_limit
            return max(0.0, round(self.main_round_limit - (now - started), 1))
        else:
            key = (uid, self.sudden_round)
            started = self.sudden_question_started_at.get(key)
            if not started:
                return self.sudden_word_limit
            return max(0.0, round(self.sudden_word_limit - (now - started), 1))


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
        uid = int(user_tg_id)
        if not self._is_member(uid):
            return False, "Вы не являетесь участником этой дуэли"
        if self.status == "finished":
            return True, "Дуэль уже завершена"
        if self.status != "playing":
            return False, "Дуэль сейчас недоступна"

        self._ensure_timer_started(uid)
        self._check_timeouts()
        if self.status == "finished":
            return True, "Время вышло! Дуэль завершена"

        answers = self.answers.setdefault(uid, [])
        if len(answers) >= self.round_size:
            return False, "Вы уже закончили — дождитесь соперника"

        if not isinstance(move_data, dict):
            if move_data is not None:
                move_data = {"answer": move_data}
            else:
                return False, "Нужен ответ на вопрос"
        elif "answer" not in move_data:
            return False, "Нужен ответ на вопрос"

        raw_answer = move_data.get("answer")

        if raw_answer == "__timeout__":
            self._finish_timeout_forfeit(uid)
            return True, "Время вышло! Дуэль завершена"

        # Защита от случайного отправления пустого ответа
        if raw_answer is None or (isinstance(raw_answer, str) and not raw_answer.strip()):
            return False, "Введите ответ на вопрос"

        now = time.time()
        if self.sudden_round == 0:
            started = self.player_started_at.get(uid, now)
            if (now - started) > (self.main_round_limit + GRACE_PERIOD):
                self._finish_timeout_forfeit(uid)
                return True, "Время раунда вышло! Дуэль завершена"
        else:
            key = (uid, self.sudden_round)
            started = self.sudden_question_started_at.get(key, now)
            if (now - started) > (self.sudden_word_limit + GRACE_PERIOD):
                self._finish_timeout_forfeit(uid)
                return True, "Время на слово вышло! Дуэль завершена"

        question = self._current_question(uid)
        if not question:
            return False, "Вопрос недоступен"
        answers.append(self._is_correct(question, raw_answer))
        self.questions[uid] = None
        if len(answers) == self.round_size:
            logger.info(
                "EGE duel player finished room=%s player=%s errors=%s waiting_for_opponent=%s",
                self.room_id, uid, self._errors(uid), not self._both_finished(),
            )
        self._finalize_if_ready()
        if self.status == "finished":
            return True, "Дуэль завершена"
        if self.sudden_round > 0 and len(answers) < self.round_size:
            return True, "Внезапная смерть! Дополнительный раунд"
        if self._finished(uid):
            return True, "Результат сохранён — ждём соперника"
        return True, "Ответ принят"

    def request_rematch(self, user_tg_id: int) -> tuple[bool, str]:
        if self.status != "finished" or not self._is_member(user_tg_id):
            return False, "Реванш пока недоступен"
        if self.rematch_requested_by and self.rematch_requested_by != int(user_tg_id):
            self.status, self.winner, self.finished_at = "playing", None, None
            self.answers = {self.host_tg_id: [], int(self.opponent_tg_id): []}
            self.questions, self.rematch_requested_by = {}, None
            self.rating_settled, self.rating_changes, self.rating_snapshots = False, {}, {}
            self.results_notified = False
            self.round_size, self.sudden_round = 10, 0
            self.player_started_at, self.sudden_question_started_at = {}, {}
            self._init_deck()
            return True, "Реванш начат"
        self.rematch_requested_by = int(user_tg_id)
        return True, "Запрос на реванш отправлен"

    def to_dict(self, viewer_tg_id: Optional[int] = None) -> dict:
        viewer = int(viewer_tg_id) if viewer_tg_id else None
        if viewer:
            self._ensure_timer_started(viewer)
        self._check_timeouts()

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

        timer_limit = self.sudden_word_limit if self.sudden_round > 0 else self.main_round_limit

        time_remaining = self.get_time_remaining(viewer)
        timer_mode = "sudden" if self.sudden_round > 0 else "main"

        return {
            "room_id": self.room_id, "game_type": self.game_type, "status": self.status,
            "matchmaking_search": self.matchmaking_search,
            "matchmaking_recipient_count": self.matchmaking_recipient_count,
            "host": {"tg_id": self.host_tg_id, "name": self.host_name},
            "opponent": {"tg_id": self.opponent_tg_id, "name": self.opponent_name} if self.opponent_tg_id else None,
            "your_answers": your_answers, "opponent_answers": rival_answers,
            "your_errors": your_errors, "opponent_errors": rival_errors,
            "your_score": your_answers - your_errors, "opponent_score": rival_answers - rival_errors,
            "your_finished": self._finished(viewer), "opponent_finished": self._finished(rival),
            "round_size": self.round_size, "sudden_round": self.sudden_round,
            "is_sudden_death": self.sudden_round > 0,
            "timer_limit": timer_limit, "time_remaining": time_remaining, "timer_mode": timer_mode,
            "winner": self.winner, "winner_name": winner_name, "result": result,
            "rematch_requested_by": self.rematch_requested_by,
            "question": self.question_for(viewer) if self.status == "playing" and viewer else None,
        }
