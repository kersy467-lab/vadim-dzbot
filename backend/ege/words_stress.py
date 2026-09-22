"""Official FIPI codifier 2026 stress dictionary and question generator."""
from __future__ import annotations

import json
from pathlib import Path
import secrets
from typing import Any, Iterable

VOWELS = "аеёиоуыэюя"
VOWELS_UPPER = "АЕЁИОУЫЭЮЯ"

_DATA_FILE = Path(__file__).resolve().parent / "words_stress_data.json"
STRESS_WORDS_FIPI: tuple[str, ...] = tuple(json.loads(_DATA_FILE.read_text(encoding="utf-8")))


def create_stress_question(source_word: str) -> dict[str, Any]:
    """Build a deterministic question dictionary from a FIPI stress-marked word."""
    target_idx = next(index for index, char in enumerate(source_word) if char in VOWELS_UPPER)
    display = source_word.lower()
    return {
        "id": secrets.token_hex(8),
        "mode": "stress",
        "word": display,
        "vowel_indexes": [index for index, char in enumerate(display) if char in VOWELS],
        "answer": target_idx,
    }


def pick_unique_stress_questions(count: int, exclude_words: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Pick up to count unique stress questions excluding already used lowercase words."""
    excluded = {w.lower() for w in exclude_words}
    available = [w for w in STRESS_WORDS_FIPI if w.lower() not in excluded]
    if not available:
        available = list(STRESS_WORDS_FIPI)
    shuffled = list(available)
    secrets.SystemRandom().shuffle(shuffled)
    chosen = shuffled[:count]
    return [create_stress_question(w) for w in chosen]
