"""
Пакет игры «Слоты» для Telegram-бота и Mini App.
"""
from backend.bot.game_slots.engine import (
    SLOT_SYMBOLS,
    spin_reels,
    evaluate_slots,
    play_slots,
)

__all__ = [
    "SLOT_SYMBOLS",
    "spin_reels",
    "evaluate_slots",
    "play_slots",
]
