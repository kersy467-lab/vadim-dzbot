import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bot.game_roulette import (
    RED_NUMBERS,
    BLACK_NUMBERS,
    get_number_color,
    check_bet_won,
    evaluate_roulette_spin,
)
from backend.db.models import User


def test_roulette_rules():
    assert get_number_color(0) == "green"
    assert get_number_color(7) == "red"
    assert get_number_color(8) == "black"

    # Red / Black
    assert check_bet_won("red", None, 7) is True
    assert check_bet_won("red", None, 8) is False
    assert check_bet_won("red", None, 0) is False  # Zero loses outside bets

    assert check_bet_won("black", None, 8) is True
    assert check_bet_won("black", None, 7) is False
    assert check_bet_won("black", None, 0) is False

    # Even / Odd
    assert check_bet_won("even", None, 8) is True
    assert check_bet_won("even", None, 7) is False
    assert check_bet_won("even", None, 0) is False

    assert check_bet_won("odd", None, 7) is True
    assert check_bet_won("odd", None, 8) is False
    assert check_bet_won("odd", None, 0) is False

    # Low / High
    assert check_bet_won("low", None, 18) is True
    assert check_bet_won("low", None, 19) is False
    assert check_bet_won("high", None, 19) is True
    assert check_bet_won("high", None, 18) is False

    # Dozens
    assert check_bet_won("dozen1", None, 12) is True
    assert check_bet_won("dozen2", None, 13) is True
    assert check_bet_won("dozen3", None, 25) is True

    # Straight
    assert check_bet_won("straight", 0, 0) is True
    assert check_bet_won("straight", 7, 7) is True
    assert check_bet_won("straight", 7, 8) is False


def test_roulette_evaluation():
    bets = [
        {"type": "red", "amount": 50},
        {"type": "straight", "value": 7, "amount": 10},
        {"type": "black", "amount": 20},
    ]
    # Winning number 7 (Red, Odd, Low, Dozen1)
    stake, payout, evals = evaluate_roulette_spin(bets, 7)
    assert stake == 80
    assert evals[0]["is_won"] is True
    assert evals[0]["payout"] == 100
    assert evals[1]["is_won"] is True
    assert evals[1]["payout"] == 360
    assert evals[2]["is_won"] is False
    assert evals[2]["payout"] == 0
    assert payout == 460


async def test_roulette_api():
    from fastapi.testclient import TestClient
    from backend.main import app

    test_user = User(
        id=1,
        tg_id=888888,
        coins=500,
        currency_ecosystem_enabled=True,
    )
    client = TestClient(app)

    # 1. Проверка блокировки при выключенной экосистеме
    with patch("backend.api.routers.roulette.router._resolve_user_and_check_ecosystem") as mock_auth:
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=400, detail="Включите игровую экосистему")
        resp = client.get("/api/roulette/state")
        assert resp.status_code == 400
        assert "экосистем" in resp.json()["detail"]

    # 2. Успешное вращение рулетки
    with patch("backend.api.routers.roulette.router._resolve_user_and_check_ecosystem", return_value=(888888, test_user)):
        with patch("backend.api.routers.roulette.router.add_user_coins", new=AsyncMock()) as mock_add_coins:
            with patch("backend.api.routers.roulette.router.get_user_by_tg_id") as mock_get_user:
                mock_user_after = User(tg_id=888888, coins=550, currency_ecosystem_enabled=True)
                mock_get_user.return_value = mock_user_after

                with patch("backend.api.routers.roulette.router.spin_wheel", return_value=7):
                    spin_resp = client.post("/api/roulette/spin", json={
                        "bets": [{"type": "red", "amount": 50}]
                    })
                    assert spin_resp.status_code == 200
                    data = spin_resp.json()
                    assert data["ok"] is True
                    assert data["winning_number"] == 7
                    assert data["color"] == "red"
                    assert data["total_payout"] == 100
                    assert data["net_profit"] == 50


if __name__ == "__main__":
    test_roulette_rules()
    test_roulette_evaluation()
    asyncio.run(test_roulette_api())
    print("=== ALL ROULETTE TESTS PASSED SUCCESSFULLY! ===")
