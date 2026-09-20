"""
Движок игры «Подбрасывание монетки» (Орёл / Решка) на монеты.
"""
import random
from typing import Dict, Any

SIDES = {
    "heads": {"id": "heads", "name": "Орёл", "icon": "🦅"},
    "tails": {"id": "tails", "name": "Решка", "icon": "👑"},
}


def flip_coin(stake: int, choice: str) -> Dict[str, Any]:
    """
    Бросок монетки:
    choice: 'heads' (орёл) или 'tails' (решка).
    Шанс 50/50.
    Выплата при победе: 2x (чистая прибыль +1x stake).
    """
    normalized_choice = choice.lower().strip()
    if normalized_choice not in SIDES:
        normalized_choice = "heads"

    outcome = random.choice(["heads", "tails"])
    is_win = (outcome == normalized_choice)

    multiplier = 2.0 if is_win else 0.0
    payout = int(round(stake * multiplier)) if is_win else 0
    net_profit = payout - stake

    return {
        "stake": stake,
        "choice": normalized_choice,
        "choice_name": SIDES[normalized_choice]["name"],
        "choice_icon": SIDES[normalized_choice]["icon"],
        "outcome": outcome,
        "outcome_name": SIDES[outcome]["name"],
        "outcome_icon": SIDES[outcome]["icon"],
        "status": "win" if is_win else "loss",
        "multiplier": multiplier,
        "payout": payout,
        "net_profit": net_profit,
    }
