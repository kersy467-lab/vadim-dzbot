import random
from typing import Dict, Any, List, Tuple

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

PAYOUT_MULTIPLIERS = {
    "straight": 36,  # 35:1 net (returns 36x stake)
    "red": 2,        # 1:1 net (returns 2x stake)
    "black": 2,      # 1:1 net
    "even": 2,       # 1:1 net
    "odd": 2,        # 1:1 net
    "low": 2,        # 1:1 net (1-18)
    "high": 2,       # 1:1 net (19-36)
    "dozen1": 3,     # 2:1 net (1-12)
    "dozen2": 3,     # 2:1 net (13-24)
    "dozen3": 3,     # 2:1 net (25-36)
}


def get_number_color(num: int) -> str:
    if num == 0:
        return "green"
    return "red" if num in RED_NUMBERS else "black"


def spin_wheel() -> int:
    """Генерация случайного сектора рулетки от 0 до 36."""
    return random.randint(0, 36)


def check_bet_won(bet_type: str, bet_val: Any, winning_num: int) -> bool:
    """Проверяет, выиграла ли конкретная ставка."""
    if bet_type == "straight":
        return int(bet_val) == winning_num

    # При выпадении 0 (Зеро) все внешние ставки проигрывают
    if winning_num == 0:
        return False

    if bet_type == "red":
        return winning_num in RED_NUMBERS
    if bet_type == "black":
        return winning_num in BLACK_NUMBERS
    if bet_type == "even":
        return winning_num % 2 == 0
    if bet_type == "odd":
        return winning_num % 2 != 0
    if bet_type == "low":
        return 1 <= winning_num <= 18
    if bet_type == "high":
        return 19 <= winning_num <= 36
    if bet_type == "dozen1":
        return 1 <= winning_num <= 12
    if bet_type == "dozen2":
        return 13 <= winning_num <= 24
    if bet_type == "dozen3":
        return 25 <= winning_num <= 36

    return False


def evaluate_roulette_spin(
    bets: List[Dict[str, Any]],
    winning_num: int
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Рассчитывает выплаты по списку ставок.
    Каждая ставка: {"type": str, "value": Any, "amount": int}
    Возвращает (total_stake, total_payout, evaluated_bets).
    """
    total_stake = 0
    total_payout = 0
    evaluated = []

    for b in bets:
        b_type = str(b.get("type", "")).lower()
        b_val = b.get("value")
        amount = max(0, int(b.get("amount", 0)))
        total_stake += amount

        is_won = check_bet_won(b_type, b_val, winning_num)
        mult = PAYOUT_MULTIPLIERS.get(b_type, 0)
        payout = amount * mult if is_won else 0
        total_payout += payout

        evaluated.append({
            "type": b_type,
            "value": b_val,
            "amount": amount,
            "is_won": is_won,
            "payout": payout,
            "net": payout - amount,
        })

    return total_stake, total_payout, evaluated
