import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bot.game_blackjack import Card, Deck, calculate_hand_value, BlackjackGame
from backend.db.models import User


def test_card_values_and_hand_calculation():
    # Числовые карты и картинки
    c_2 = Card("♠", "2")
    c_10 = Card("♥", "10")
    c_j = Card("♦", "J")
    c_q = Card("♣", "Q")
    c_k = Card("♠", "K")
    assert c_2.base_value == 2
    assert c_10.base_value == 10
    assert c_j.base_value == 10
    assert c_q.base_value == 10
    assert c_k.base_value == 10

    # Мягкий туз (A + 6 = 17 soft)
    c_a = Card("♥", "A")
    c_6 = Card("♦", "6")
    val, is_soft = calculate_hand_value([c_a, c_6])
    assert val == 17
    assert is_soft is True

    # Перебор смягчается тузом (A + 6 + 10 = 17 hard)
    val, is_soft = calculate_hand_value([c_a, c_6, c_10])
    assert val == 17
    assert is_soft is False

    # Два туза (A + A = 12 soft)
    c_a2 = Card("♠", "A")
    val, is_soft = calculate_hand_value([c_a, c_a2])
    assert val == 12
    assert is_soft is True

    # Три туза (A + A + A = 13 soft)
    c_a3 = Card("♦", "A")
    val, is_soft = calculate_hand_value([c_a, c_a2, c_a3])
    assert val == 13
    assert is_soft is True


def test_deck_operations():
    deck = Deck(shuffle=False)
    assert deck.remaining == 52
    drawn = deck.draw()
    assert isinstance(drawn, Card)
    assert deck.remaining == 51


def test_blackjack_game_logic():
    # 1. Натуральный блэкджек (3:2 выплата)
    game = BlackjackGame(stake=100)
    game.deck = MagicDrawMock([
        Card("♠", "A"), Card("♥", "K"),  # Игрок: 21
        Card("♦", "9"), Card("♣", "10")   # Дилер: 19
    ])
    state = game.deal(100)
    assert state["phase"] == "done"
    assert state["status"] == "blackjack"
    assert state["payout"] == 250  # 100 + 150 (3:2)
    assert state["net_profit"] == 150

    # 2. Пуш при обоюдном блэкджеке (возврат 100%)
    game2 = BlackjackGame(stake=100)
    game2.deck = MagicDrawMock([
        Card("♠", "A"), Card("♥", "K"),  # Игрок: 21
        Card("♦", "A"), Card("♣", "J")   # Дилер: 21
    ])
    state2 = game2.deal(100)
    assert state2["phase"] == "done"
    assert state2["status"] == "push"
    assert state2["payout"] == 100
    assert state2["net_profit"] == 0

    # 3. Добор (Hit) и перебор (Bust)
    game3 = BlackjackGame(stake=50)
    game3.deck = MagicDrawMock([
        Card("♠", "10"), Card("♥", "6"),  # Игрок: 16
        Card("♦", "7"), Card("♣", "8"),   # Дилер: 15
        Card("♠", "K")                    # Добор: 16 + 10 = 26 (Bust)
    ])
    game3.deal(50)
    state3 = game3.hit()
    assert state3["phase"] == "done"
    assert state3["status"] == "player_bust"
    assert state3["payout"] == 0

    # 4. Остановка (Stand) и добор дилера до 17+
    game4 = BlackjackGame(stake=50)
    game4.deck = MagicDrawMock([
        Card("♠", "10"), Card("♥", "9"),  # Игрок: 19
        Card("♦", "8"), Card("♣", "6"),   # Дилер: 14 (<17)
        Card("♠", "4")                    # Добор дилера: 14 + 4 = 18
    ])
    game4.deal(50)
    state4 = game4.stand()
    assert state4["phase"] == "done"
    assert state4["status"] == "player_win"
    assert state4["payout"] == 100  # 1:1
    assert state4["net_profit"] == 50

    # 5. Удвоение (Double Down)
    game5 = BlackjackGame(stake=40)
    game5.deck = MagicDrawMock([
        Card("♠", "5"), Card("♥", "6"),  # Игрок: 11
        Card("♦", "10"), Card("♣", "7"), # Дилер: 17
        Card("♠", "10")                  # Добор игрока при удвоении: 11 + 10 = 21
    ])
    game5.deal(40)
    assert game5.stake == 40
    state5 = game5.double_down()
    assert state5["phase"] == "done"
    assert state5["status"] == "player_win"
    assert state5["stake"] == 80
    assert state5["payout"] == 160  # 1:1 от 80
    assert state5["net_profit"] == 80


class MagicDrawMock:
    def __init__(self, cards):
        self.cards = list(cards)

    @property
    def remaining(self):
        return 52

    def draw(self):
        if self.cards:
            return self.cards.pop(0)
        return Card("♠", "2")



async def test_blackjack_api_endpoints():
    from fastapi.testclient import TestClient
    from backend.main import app

    test_user = User(
        id=1,
        tg_id=777777,
        full_name="Казино Тестер",
        coins=500,
        currency_ecosystem_enabled=True,
    )

    client = TestClient(app)

    # 1. Проверка блокировки при выключенной экосистеме
    with patch("backend.api.routers.blackjack.router._resolve_user_and_check_ecosystem") as mock_auth:
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=400, detail="Включите игровую экосистему")
        resp = client.get("/api/blackjack/state")
        assert resp.status_code == 400
        assert "экосистем" in resp.json()["detail"]

    # 2. Успешная раздача и списание монет
    with patch("backend.api.routers.blackjack.router._resolve_user_and_check_ecosystem", return_value=(777777, test_user)):
        with patch("backend.api.routers.blackjack.router.add_user_coins", new=AsyncMock()) as mock_add_coins:
            with patch("backend.api.routers.blackjack.router.get_user_by_tg_id") as mock_get_user:
                mock_user_after_stake = User(tg_id=777777, coins=450, currency_ecosystem_enabled=True)
                mock_get_user.return_value = mock_user_after_stake

                deal_resp = client.post("/api/blackjack/deal", json={"stake": 50})
                assert deal_resp.status_code == 200
                data = deal_resp.json()
                assert data["ok"] is True
                assert data["coins"] == 450
                assert data["state"]["stake"] == 50
                # Ставка 50 была списана
                mock_add_coins.assert_any_call(mock_add_coins.call_args[0][0], 777777, -50)


if __name__ == "__main__":
    test_card_values_and_hand_calculation()
    test_deck_operations()
    test_blackjack_game_logic()
    asyncio.run(test_blackjack_api_endpoints())
    print("=== ALL BLACKJACK TESTS PASSED SUCCESSFULLY! ===")
