"""
Тестирование многопользовательского стола «Блэкджек» (2–4 игрока против Дилера).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.bot.game_blackjack.cards import Card, calculate_hand_value
from backend.bot.game_blackjack.table_game import BlackjackTableGame, TablePlayer


def test_table_initialization_and_capacity():
    table = BlackjackTableGame(max_players=3, min_stake=25)
    assert table.max_players == 3
    assert table.min_stake == 25
    assert len(table.players) == 0

    assert table.add_player(101, "Иван") is True
    assert table.add_player(102, "Алексей") is True
    assert table.add_player(103, "Мария") is True
    # Превышение лимита мест (макс 3)
    assert table.add_player(104, "Ольга") is False
    assert len(table.players) == 3

    # Удаление игрока
    assert table.remove_player(102) is True
    assert len(table.players) == 2
    assert table.players[1].user_id == 103


def test_table_betting_and_deal():
    table = BlackjackTableGame(max_players=4, min_stake=10)
    table.add_player(1, "Alice")
    table.add_player(2, "Bob")

    # Ставка меньше минимума
    res = table.place_bet(1, 5)
    assert res["ok"] is False

    # Корректные ставки
    res1 = table.place_bet(1, 20)
    assert res1["ok"] is True
    assert res1["all_ready"] is False  # Bob еще не поставил

    res2 = table.place_bet(2, 50)
    assert res2["ok"] is True
    assert res2["all_ready"] is True  # Все готовы

    # Раздача
    deal_res = table.start_deal()
    assert deal_res["ok"] is True
    assert len(table.dealer_cards) == 2
    assert len(table.players[0].cards) == 2
    assert len(table.players[1].cards) == 2

    # Состояние стола: одна карта дилера скрыта
    state = table.to_dict()
    assert state["dealer_cards"][1].get("hidden") is True
    assert state["phase"] == "player_turns"


def test_table_turns_and_dealer_settlement():
    table = BlackjackTableGame(max_players=2, min_stake=10)
    table.add_player(10, "Player1")
    table.add_player(20, "Player2")

    table.place_bet(10, 100)
    table.place_bet(20, 100)
    table.start_deal()

    # Фиксируем карты игроков и дилера вручную для детерминированного теста
    # Player1: 10 + 9 = 19
    table.players[0].cards = [Card("♠", "10"), Card("♥", "9")]
    table.players[0].status = "acting"
    table.active_player_idx = 0

    # Player2: 8 + 8 = 16
    table.players[1].cards = [Card("♦", "8"), Card("♣", "8")]
    table.players[1].status = "waiting_turn"

    # Дилер: 10 + 6 = 16 (должен добрать до 17+)
    table.dealer_cards = [Card("♠", "10"), Card("♥", "6")]

    # Player1 решает остановиться (stand)
    stand_res1 = table.player_stand(10)
    assert stand_res1["ok"] is True
    assert table.players[0].status == "stand"

    # Ход перешел к Player2
    assert table.get_active_player().user_id == 20
    assert table.players[1].status == "acting"

    # Player2 тоже останавливается (stand)
    stand_res2 = table.player_stand(20)
    assert stand_res2["ok"] is True

    # Раунд должен перейти в settled после хода дилера
    assert table.phase == "settled"

    d_score, _ = calculate_hand_value(table.dealer_cards)
    assert d_score >= 17  # Дилер обязан добрать до 17+

    # Проверяем независимость выплат:
    p1 = table.players[0]
    p2 = table.players[1]
    p1_score, _ = calculate_hand_value(p1.cards)
    p2_score, _ = calculate_hand_value(p2.cards)

    if d_score > 21:
        assert p1.status == "win" and p1.payout == 200
        assert p2.status == "win" and p2.payout == 200
    else:
        if p1_score > d_score:
            assert p1.status == "win" and p1.payout == 200
        elif p1_score == d_score:
            assert p1.status == "push" and p1.payout == 100
        else:
            assert p1.status == "dealer_win" and p1.payout == 0

        if p2_score > d_score:
            assert p2.status == "win" and p2.payout == 200
        elif p2_score == d_score:
            assert p2.status == "push" and p2.payout == 100
        else:
            assert p2.status == "dealer_win" and p2.payout == 0


def test_table_natural_blackjack_3_to_2():
    table = BlackjackTableGame(max_players=2, min_stake=10)
    table.add_player(100, "Lucky")
    table.place_bet(100, 200)

    # Имитируем натуральный блэкджек у игрока (Ace + King = 21)
    table.players[0].cards = [Card("♠", "A"), Card("♥", "K")]
    table.players[0].status = "blackjack"
    table.dealer_cards = [Card("♦", "9"), Card("♣", "8")]  # дилер 17

    table.settle_results()
    assert table.players[0].status == "blackjack"
    assert table.players[0].payout == 200 + int(200 * 1.5)  # 500 монет (3:2)
    assert table.players[0].net_profit == 300
    print("[OK] test_table_natural_blackjack_3_to_2 passed.")


if __name__ == "__main__":
    test_table_initialization_and_capacity()
    test_table_betting_and_deal()
    test_table_turns_and_dealer_settlement()
    test_table_natural_blackjack_3_to_2()
    print("=== ALL BLACKJACK TABLE TESTS PASSED! ===")
