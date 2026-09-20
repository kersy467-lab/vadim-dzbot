"""
Движок игры «Слоты» (Однорукий бандит) на 3 барабана.
"""
import random
from typing import List, Dict, Any

SLOT_SYMBOLS = [
    {"symbol": "🍒", "name": "Вишня", "weight": 16, "triple_mult": 7, "pair_mult": 1.5},
    {"symbol": "🍋", "name": "Лимон", "weight": 28, "triple_mult": 7, "pair_mult": 0.5},
    {"symbol": "🍇", "name": "Виноград", "weight": 24, "triple_mult": 10, "pair_mult": 0.9},
    {"symbol": "🔔", "name": "Колокольчик", "weight": 14, "triple_mult": 15, "pair_mult": 2.0},
    {"symbol": "💎", "name": "Алмаз", "weight": 6, "triple_mult": 30, "pair_mult": 2.5},
    {"symbol": "7️⃣", "name": "Семёрка", "weight": 3, "triple_mult": 50, "pair_mult": 3.0},
]

_SYMBOLS_LIST = [s["symbol"] for s in SLOT_SYMBOLS]
_WEIGHTS_LIST = [s["weight"] for s in SLOT_SYMBOLS]
_LOOKUP = {s["symbol"]: s for s in SLOT_SYMBOLS}


def spin_reels() -> List[str]:
    """Вращение 3 барабанов со взвешенной вероятностью."""
    return random.choices(_SYMBOLS_LIST, weights=_WEIGHTS_LIST, k=3)


def evaluate_slots(reels: List[str], stake: int) -> Dict[str, Any]:
    """
    Расчет выигрыша по выпавшим 3 символам (RTP ~100%):
    - 3 одинаковых: множитель triple_mult (до 50x)
    - 2 одинаковых: множитель pair_mult (0.5x .. 3.0x)
    - Иначе: 0
    """
    if len(reels) != 3:
        raise ValueError("Слоты требуют ровно 3 барабана")

    s1, s2, s3 = reels
    mult = 0.0
    status = "loss"
    combo_name = "Нет совпадений"

    if s1 == s2 == s3:
        info = _LOOKUP.get(s1, {})
        mult = float(info.get("triple_mult", 5))
        combo_name = f"Три {info.get('name', s1)}!"
        status = "jackpot" if s1 == "7️⃣" else ("big_win" if mult >= 12 else "win")
    elif s1 == s2 or s2 == s3 or s1 == s3:
        match_sym = s1 if (s1 == s2 or s1 == s3) else s2
        info = _LOOKUP.get(match_sym, {})
        mult = float(info.get("pair_mult", 1.0))
        combo_name = f"Пара {info.get('name', match_sym)}"
        status = "win" if mult > 1.0 else ("push" if mult == 1.0 else "loss")

    payout = int(round(stake * mult))
    net_profit = payout - stake

    return {
        "reels": reels,
        "stake": stake,
        "multiplier": mult,
        "payout": payout,
        "net_profit": net_profit,
        "status": status,
        "combination": combo_name,
    }


def play_slots(stake: int) -> Dict[str, Any]:
    """Полный раунд слотов: вращение + расчет выигрыша."""
    reels = spin_reels()
    return evaluate_slots(reels, stake)
