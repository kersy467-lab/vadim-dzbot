"""
Пакет чистой логики игры «Дурак».
100% обратная совместимость с прежним модулем backend.bot.game_durak.
"""
from .cards import Card, Deck, SUITS, RANKS, RANK_ORDER
from .game import DurakGame

__all__ = [
    "Card",
    "Deck",
    "SUITS",
    "RANKS",
    "RANK_ORDER",
    "DurakGame",
]
