"""
Логика ходов бота для игры «Дурак».
"""
from typing import Optional, TYPE_CHECKING
from .cards import Card, RANK_ORDER

if TYPE_CHECKING:
    from .game import DurakGame


def make_bot_move(game: "DurakGame") -> Optional[dict]:
    """
    Выполнить ход за бота. Возвращает описание действия или None.
    """
    if game.phase == "done":
        return None

    # Фаза 1: Бот атакует
    if game.phase == "attack" and game.current_attacker in game.bot_indices:
        hand = game.hands[game.current_attacker]
        if not hand:
            return game.pass_attack(game.current_attacker)

        if game.table:
            ranks_on_table = set()
            for slot in game.table:
                ranks_on_table.add(slot["attack"]["rank"])
                if slot.get("defend"):
                    ranks_on_table.add(slot["defend"]["rank"])
            candidates = [c for c in hand if c["rank"] in ranks_on_table]
        else:
            candidates = list(hand)

        if not candidates:
            return game.pass_attack(game.current_attacker)

        non_trump = [c for c in candidates if c["suit"] != game.trump_suit]
        if non_trump:
            choice = min(non_trump, key=lambda c: RANK_ORDER[c["rank"]])
        else:
            choice = min(candidates, key=lambda c: RANK_ORDER[c["rank"]])

        result = game.attack(game.current_attacker, choice)
        if not result.get("ok"):
            return game.pass_attack(game.current_attacker)
        return {"action": "attack", "card": choice, "result": result}

    # Фаза 2: Бот защищается
    elif game.phase == "defend" and game.current_defender in game.bot_indices:
        hand = game.hands[game.current_defender]
        open_slots = [s for s in game.table if s["defend"] is None]
        if not open_slots:
            return None

        slot = open_slots[0]
        atk_card = Card.from_dict(slot["attack"])

        best_def = None
        best_def_dict = None
        for cd in hand:
            c = Card.from_dict(cd)
            if c.beats(atk_card, game.trump_suit):
                if best_def is None:
                    best_def = c
                    best_def_dict = cd
                else:
                    if best_def.suit == game.trump_suit and c.suit != game.trump_suit:
                        best_def = c
                        best_def_dict = cd
                    elif best_def.suit == c.suit and RANK_ORDER[c.rank] < RANK_ORDER[best_def.rank]:
                        best_def = c
                        best_def_dict = cd

        if best_def_dict:
            result = game.defend(game.current_defender, slot["attack"], best_def_dict)
            return {"action": "defend", "card": best_def_dict, "result": result}
        else:
            result = game.take(game.current_defender)
            return {"action": "take", "result": result}

    return None
