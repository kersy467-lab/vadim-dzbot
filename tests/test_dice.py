import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bot.game_dice import roll_dice, play_dice_duel, play_dice_over_under
from backend.db.models import User


def test_dice_engine():
    # roll_dice
    dice = roll_dice(2)
    assert len(dice) == 2
    assert 1 <= dice[0] <= 6
    assert 1 <= dice[1] <= 6

    # play_dice_duel
    with patch("backend.bot.game_dice.engine.roll_dice") as mock_roll:
        # 1. Победа игрока без дубля (1:1)
        mock_roll.side_effect = [[6, 4], [3, 2]]
        res = play_dice_duel(50)
        assert res["status"] == "win"
        assert res["payout"] == 100
        assert res["net_profit"] == 50

        # 2. Победа с дублем (выплата 2x, статус super_win для анимации)
        mock_roll.side_effect = [[5, 5], [3, 2]]
        res2 = play_dice_duel(50)
        assert res2["status"] == "super_win"
        assert res2["payout"] == 100
        assert res2["net_profit"] == 50

        # 3. Ничья (Push)
        mock_roll.side_effect = [[4, 3], [5, 2]]
        res3 = play_dice_duel(50)
        assert res3["status"] == "push"
        assert res3["payout"] == 50
        assert res3["net_profit"] == 0

        # 4. Поражение
        mock_roll.side_effect = [[2, 3], [6, 4]]
        res4 = play_dice_duel(50)
        assert res4["status"] == "loss"
        assert res4["payout"] == 0
        assert res4["net_profit"] == -50

    # play_dice_over_under
    with patch("backend.bot.game_dice.engine.roll_dice") as mock_roll:
        # under_7 победа
        mock_roll.return_value = [2, 3] # 5
        ou1 = play_dice_over_under(40, "under_7")
        assert ou1["is_won"] is True
        assert ou1["payout"] == 80

        # over_7 победа
        mock_roll.return_value = [5, 4] # 9
        ou2 = play_dice_over_under(40, "over_7")
        assert ou2["is_won"] is True
        assert ou2["payout"] == 80

        # exact_7 победа (4:1 чистый, 5x выплата)
        mock_roll.return_value = [3, 4] # 7
        ou3 = play_dice_over_under(40, "exact_7")
        assert ou3["is_won"] is True
        assert ou3["payout"] == 200

        # double победа
        mock_roll.return_value = [4, 4]
        ou4 = play_dice_over_under(40, "double")
        assert ou4["is_won"] is True
        assert ou4["payout"] == 120


async def test_dice_api():
    from fastapi.testclient import TestClient
    from backend.main import app

    test_user = User(
        id=1,
        tg_id=999999,
        coins=500,
        currency_ecosystem_enabled=True,
    )
    client = TestClient(app)

    # 1. Проверка блокировки при выключенной экосистеме
    with patch("backend.api.routers.dice.router._resolve_user_and_check_ecosystem") as mock_auth:
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=400, detail="Включите игровую экосистему")
        resp = client.get("/api/dice/state")
        assert resp.status_code == 400
        assert "экосистем" in resp.json()["detail"]

    # 2. Успешный бросок дуэли
    with patch("backend.api.routers.dice.router._resolve_user_and_check_ecosystem", return_value=(999999, test_user)):
        with patch("backend.api.routers.dice.router.add_user_coins", new=AsyncMock()) as mock_add_coins:
            with patch("backend.api.routers.dice.router.get_user_by_tg_id") as mock_get_user:
                mock_user_after = User(tg_id=999999, coins=550, currency_ecosystem_enabled=True)
                mock_get_user.return_value = mock_user_after

                duel_resp = client.post("/api/dice/duel", json={"stake": 50})
                assert duel_resp.status_code == 200
                data = duel_resp.json()
                assert data["ok"] is True
                assert "result" in data
                assert data["result"]["mode"] == "duel"


if __name__ == "__main__":
    test_dice_engine()
    asyncio.run(test_dice_api())
    print("=== ALL DICE TESTS PASSED SUCCESSFULLY! ===")
