"""Official FIPI codifier 2026 vocabulary dictionary and question generator."""
from __future__ import annotations

import json
from pathlib import Path
import re
import secrets
from typing import Any, Iterable

VOWELS = "аеёиоуыэюя"

_DATA_FILE = Path(__file__).resolve().parent / "words_vocabulary_data.json"
VOCABULARY_WORDS_FIPI: tuple[str, ...] = tuple(json.loads(_DATA_FILE.read_text(encoding="utf-8")))


def mask_vocabulary_word(word: str) -> str:
    """Mask all vowels in a vocabulary word with underscore."""
    return "".join("_" if char.lower() in VOWELS else char for char in word)


def create_vocab_question(word: str) -> dict[str, Any]:
    """Build a deterministic question dictionary for a vocabulary word."""
    clean = str(word or "").strip().lower()
    return {
        "id": secrets.token_hex(8),
        "mode": "vocabulary",
        "word": clean,
        "masked": mask_vocabulary_word(clean),
        "answer": clean,
    }


def pick_unique_vocab_questions(count: int, exclude_words: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Pick up to count unique vocabulary questions excluding already used lowercase words."""
    excluded = {w.lower() for w in exclude_words}
    available = [w for w in VOCABULARY_WORDS_FIPI if w.lower() not in excluded]
    if not available:
        available = list(VOCABULARY_WORDS_FIPI)
    shuffled = list(available)
    secrets.SystemRandom().shuffle(shuffled)
    chosen = shuffled[:count]
    return [create_vocab_question(w) for w in chosen]
