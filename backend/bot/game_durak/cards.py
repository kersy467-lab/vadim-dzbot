"""
Карты и колода для игры «Дурак».
"""
import random
from typing import Optional

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_ORDER = {r: i for i, r in enumerate(RANKS)}


class Card:
    __slots__ = ("suit", "rank")

    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank

    def beats(self, other: "Card", trump: str) -> bool:
        """Может ли эта карта побить other?"""
        if self.suit == other.suit:
            return RANK_ORDER[self.rank] > RANK_ORDER[other.rank]
        if self.suit == trump and other.suit != trump:
            return True
        return False

    def to_dict(self) -> dict:
        return {"suit": self.suit, "rank": self.rank}

    @staticmethod
    def from_dict(d: dict) -> "Card":
        return Card(d["suit"], d["rank"])

    def __repr__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __eq__(self, other) -> bool:
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank

    def __hash__(self):
        return hash((self.suit, self.rank))


class Deck:
    def __init__(self):
        self._cards = [Card(s, r) for s in SUITS for r in RANKS]
        random.shuffle(self._cards)

    def deal(self, count: int) -> list[Card]:
        taken = self._cards[:count]
        self._cards = self._cards[count:]
        return taken

    def __len__(self) -> int:
        return len(self._cards)

    @property
    def trump_card(self) -> Optional[Card]:
        return self._cards[-1] if self._cards else None
