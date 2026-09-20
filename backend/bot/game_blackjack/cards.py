import random
from typing import List, Tuple, Dict, Any, Optional

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUIT_NAMES = {
    "♠": "spades",
    "♥": "hearts",
    "♦": "diamonds",
    "♣": "clubs",
}


class Card:
    __slots__ = ("suit", "rank")

    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank

    @property
    def suit_name(self) -> str:
        return SUIT_NAMES.get(self.suit, "spades")

    @property
    def base_value(self) -> int:
        if self.rank in ("J", "Q", "K"):
            return 10
        if self.rank == "A":
            return 11
        return int(self.rank)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suit": self.suit,
            "rank": self.rank,
            "suit_name": self.suit_name,
            "value": self.base_value,
        }

    def __repr__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Card):
            return self.suit == other.suit and self.rank == other.rank
        return False


def calculate_hand_value(cards: List[Card]) -> Tuple[int, bool]:
    """
    Вычисляет сумму очков в руке с учетом мягкого/жесткого Туза.
    Возвращает (итоговые_очки, флаг_мягкой_руки).
    """
    total = 0
    aces = 0
    for card in cards:
        if card.rank == "A":
            aces += 1
            total += 11
        elif card.rank in ("J", "Q", "K"):
            total += 10
        else:
            total += int(card.rank)

    # Превращаем Тузы из 11 в 1 при переборе
    soft_aces = aces
    while total > 21 and soft_aces > 0:
        total -= 10
        soft_aces -= 1

    is_soft = soft_aces > 0
    return total, is_soft


class Deck:
    def __init__(self, shuffle: bool = True):
        self.cards: List[Card] = [
            Card(suit, rank) for suit in SUITS for rank in RANKS
        ]
        if shuffle:
            random.shuffle(self.cards)

    def draw(self) -> Card:
        if not self.cards:
            self.cards = [Card(s, r) for s in SUITS for r in RANKS]
            random.shuffle(self.cards)
        return self.cards.pop()

    @property
    def remaining(self) -> int:
        return len(self.cards)
