import random
from typing import List, Dict, Any, Tuple


def roll_dice(count: int = 2) -> List[int]:
    """Бросок N шестигранных кубиков."""
    return [random.randint(1, 6) for _ in range(count)]


def play_dice_duel(stake: int) -> Dict[str, Any]:
    """
    Режим «Дуэль с дилером»:
    Игрок и дилер бросают по 2 кубика.
    - Победа: выплата 1:1 (2x stake).
    - Победа с дублем (например, 5-5 или 6-6): супер-выигрыш 2:1 (3x stake)!
    - Ничья: возврат ставки 100% (push).
    - Поражение: 0.
    """
    player_dice = roll_dice(2)
    dealer_dice = roll_dice(2)

    p_sum = sum(player_dice)
    d_sum = sum(dealer_dice)

    p_double = (player_dice[0] == player_dice[1])
    d_double = (dealer_dice[0] == dealer_dice[1])

    if p_sum > d_sum:
        if p_double:
            status = "super_win"
            payout = stake * 2  # Победа с дублем (RTP ровно 100%)
        else:
            status = "win"
            payout = stake * 2  # Обычная победа (1:1)
    elif p_sum < d_sum:
        status = "loss"
        payout = 0
    else:
        # При равной сумме дубль побеждает отсутствие дубля
        if p_double and not d_double:
            status = "win"
            payout = stake * 2
        elif d_double and not p_double:
            status = "loss"
            payout = 0
        else:
            status = "push"
            payout = stake

    return {
        "mode": "duel",
        "stake": stake,
        "player_dice": player_dice,
        "player_total": p_sum,
        "player_double": p_double,
        "dealer_dice": dealer_dice,
        "dealer_total": d_sum,
        "dealer_double": d_double,
        "status": status,
        "payout": payout,
        "net_profit": payout - stake,
    }


def play_dice_over_under(stake: int, prediction: str) -> Dict[str, Any]:
    """
    Режим «Больше / Меньше / 7»:
    - under_7: сумма 2..6 -> 1:1 (2x stake)
    - over_7: сумма 8..12 -> 1:1 (2x stake)
    - exact_7: сумма ровно 7 -> 4:1 (5x stake)
    - any_double: дубль -> 2:1 (3x stake)
    """
    dice = roll_dice(2)
    total = sum(dice)
    is_double = (dice[0] == dice[1])

    pred = prediction.lower().strip()
    is_won = False
    multiplier = 0

    if pred == "under_7":
        is_won = total < 7
        multiplier = 2
    elif pred == "over_7":
        is_won = total > 7
        multiplier = 2
    elif pred in ("exact_7", "seven"):
        is_won = total == 7
        multiplier = 5
    elif pred in ("double", "any_double"):
        is_won = is_double
        multiplier = 3

    payout = (stake * multiplier) if is_won else 0

    return {
        "mode": "over_under",
        "stake": stake,
        "prediction": pred,
        "dice": dice,
        "total": total,
        "is_double": is_double,
        "is_won": is_won,
        "payout": payout,
        "net_profit": payout - stake,
    }
