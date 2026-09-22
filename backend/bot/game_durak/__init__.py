"""
Пакет чистой логики игры «Дурак».
100% обратная совместимость с прежним модулем backend.bot.game_durak.
"""
from .cards import Card, Deck, SUITS, RANKS, RANK_ORDER
from .game import DurakGame
from .bot import make_bot_move

__all__ = [
    "Card",
    "Deck",
    "SUITS",
    "RANKS",
    "RANK_ORDER",
    "DurakGame",
    "make_bot_move",
]
