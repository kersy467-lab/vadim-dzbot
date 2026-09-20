"""
Пакет игры «Подбрасывание монетки» для Telegram-бота и Mini App.
"""
from backend.bot.game_coinflip.engine import (
    SIDES,
    flip_coin,
)

__all__ = [
    "SIDES",
    "flip_coin",
]
