import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bot.game_durak import DurakGame, Card, RANK_ORDER


def test_game_initialization():
    game = DurakGame(player_ids=[101, 102], bot_indices=[102], stake=50)
    assert len(game.hands[101]) == 6
    assert len(game.hands[102]) == 6
    assert game.trump_suit in ["♠", "♥", "♦", "♣"]
    assert game.current_attacker in [101, 102]
    assert game.current_defender in [101, 102]
    assert game.current_attacker != game.current_defender
    assert game.phase == "attack"
    assert game.total_pot == 100


def test_attack_and_podkidnoy_rules():
    game = DurakGame(player_ids=[1, 2])
    game.trump_suit = "♦"
    game.current_attacker = 1
    game.current_defender = 2

    game.hands[1] = [
        {"suit": "♠", "rank": "7"},
        {"suit": "♥", "rank": "7"},
        {"suit": "♣", "rank": "9"},
    ]
    game.hands[2] = [
        {"suit": "♠", "rank": "8"},
        {"suit": "♥", "rank": "10"},
    ]

    # 1. Первая атака картой 7♠
    res = game.attack(1, {"suit": "♠", "rank": "7"})
    assert res.get("ok") is True
    assert len(game.table) == 1
    assert game.phase == "defend"

    # 2. Нельзя атаковать не в фазу атаки
    res_err = game.attack(1, {"suit": "♥", "rank": "7"})
    assert res_err.get("ok") is False
    assert "не фаза атаки" in res_err.get("error")

    # 3. Защитник отбивает 7♠ картой 8♠
    res_def = game.defend(2, {"suit": "♠", "rank": "7"}, {"suit": "♠", "rank": "8"})
    assert res_def.get("ok") is True
    assert game.phase == "attack"  # Все карты отбиты -> фаза снова attack

    # 4. Подкидывание не того ранга (9♣ при рангах 7 и 8 на столе)
    res_invalid_rank = game.attack(1, {"suit": "♣", "rank": "9"})
    assert res_invalid_rank.get("ok") is False
    assert "тех же рангов" in res_invalid_rank.get("error")

    # 5. Подкидывание разрешенного ранга 7♥
    res_valid = game.attack(1, {"suit": "♥", "rank": "7"})
    assert res_valid.get("ok") is True
    assert len(game.table) == 2
    assert game.phase == "defend"


def test_defend_rules_and_trumps():
    game = DurakGame(player_ids=[1, 2])
    game.trump_suit = "♦"
    game.current_attacker = 1
    game.current_defender = 2

    game.hands[1] = [{"suit": "♠", "rank": "10"}]
    game.hands[2] = [
        {"suit": "♠", "rank": "7"},   # не бьет (меньше)
        {"suit": "♥", "rank": "A"},   # не бьет (другая не козырная масть)
        {"suit": "♦", "rank": "6"},   # бьет козырем
        {"suit": "♠", "rank": "J"},   # бьет мастью выше
    ]

    game.attack(1, {"suit": "♠", "rank": "10"})

    # Меньшая карта той же масти
    assert game.defend(2, {"suit": "♠", "rank": "10"}, {"suit": "♠", "rank": "7"})["ok"] is False
    # Другая некозырная масть
    assert game.defend(2, {"suit": "♠", "rank": "10"}, {"suit": "♥", "rank": "A"})["ok"] is False
    # Козырь бьет некозырную масть
    res_trump = game.defend(2, {"suit": "♠", "rank": "10"}, {"suit": "♦", "rank": "6"})
    assert res_trump.get("ok") is True
    assert game.table[0]["defend"] == {"suit": "♦", "rank": "6"}


def test_take_and_refill_order():
    game = DurakGame(player_ids=[1, 2])
    game.trump_suit = "♣"
    game.current_attacker = 1
    game.current_defender = 2

    # Настроим руки и остаток колоды
    game.hands[1] = [{"suit": "♠", "rank": "6"}]
    game.hands[2] = [{"suit": "♥", "rank": "6"}]
    game.deck = [
        {"suit": "♦", "rank": "8"},   # Должен достаться атакующему (1)
        {"suit": "♦", "rank": "9"},   # Должен достаться атакующему (1)
        {"suit": "♦", "rank": "10"},  # Должен достаться атакующему (1)
        {"suit": "♦", "rank": "J"},   # Должен достаться атакующему (1)
        {"suit": "♦", "rank": "Q"},   # Должен достаться атакующему (1)
        {"suit": "♦", "rank": "K"},   # Должен достаться атакующему (1)
        {"suit": "♠", "rank": "A"},   # Должен достаться защитнику (2)
    ]

    game.attack(1, {"suit": "♠", "rank": "6"})
    # Защитник берет
    res_take = game.take(2)
    assert res_take.get("ok") is True

    # Защитник (2) забрал карту со стола
    assert {"suit": "♠", "rank": "6"} in game.hands[2]
    # Атакующий (1) первым добрал карты из колоды до 6
    assert len(game.hands[1]) == 6
    assert {"suit": "♦", "rank": "8"} in game.hands[1]

    # В игре на 2 игрока при взятии ход остается у того же атакующего
    assert game.current_attacker == 1
    assert game.current_defender == 2
    assert game.phase == "attack"


def test_pass_bito_and_turn_swap():
    game = DurakGame(player_ids=[1, 2])
    game.trump_suit = "♣"
    game.current_attacker = 1
    game.current_defender = 2

    game.hands[1] = [
        {"suit": "♠", "rank": "7"},
        {"suit": "♣", "rank": "10"},
        {"suit": "♣", "rank": "J"},
        {"suit": "♣", "rank": "Q"},
        {"suit": "♣", "rank": "K"},
        {"suit": "♣", "rank": "A"},
    ]
    game.hands[2] = [
        {"suit": "♠", "rank": "8"},
        {"suit": "♥", "rank": "10"},
        {"suit": "♥", "rank": "J"},
        {"suit": "♥", "rank": "Q"},
        {"suit": "♥", "rank": "K"},
        {"suit": "♥", "rank": "A"},
    ]
    game.deck = [
        {"suit": "♦", "rank": "A"},  # 1-му
        {"suit": "♦", "rank": "K"},  # 2-му
    ]

    game.attack(1, {"suit": "♠", "rank": "7"})
    game.defend(2, {"suit": "♠", "rank": "7"}, {"suit": "♠", "rank": "8"})

    # Атакующий говорит «Бито»
    res_pass = game.pass_attack(1)
    assert res_pass.get("ok") is True
    assert len(game.table) == 0
    assert len(game.beaten) == 2

    # Первым берет атакующий (1), затем защитник (2)
    assert {"suit": "♦", "rank": "A"} in game.hands[1]
    assert {"suit": "♦", "rank": "K"} in game.hands[2]

    # После «Бито» защитник становится новым атакующим
    assert game.current_attacker == 2
    assert game.current_defender == 1
    assert game.phase == "attack"


def test_bot_attack_and_defend_ai():
    game = DurakGame(player_ids=[1, -1], bot_indices=[-1])
    game.trump_suit = "♥"
    game.current_attacker = -1
    game.current_defender = 1
    game.phase = "attack"

    game.hands[-1] = [
        {"suit": "♥", "rank": "A"},  # козырный туз (не должен скидывать первым)
        {"suit": "♠", "rank": "7"},  # меньший некозырь
        {"suit": "♠", "rank": "10"},
    ]
    game.hands[1] = [
        {"suit": "♠", "rank": "K"},
        {"suit": "♣", "rank": "9"},
    ]

    # Бот атакует
    mv = game.bot_move()
    assert mv is not None
    assert mv["action"] == "attack"
    assert mv["card"] == {"suit": "♠", "rank": "7"}
    assert game.phase == "defend"

    # Теперь игрок 1 отбивает
    game.defend(1, {"suit": "♠", "rank": "7"}, {"suit": "♠", "rank": "K"})
    assert game.phase == "attack"

    # Бот проверяет подкидывание: у него нет 7 и нет K -> бот должен сделать pass_attack («Бито»)
    mv_pass = game.bot_move()
    assert mv_pass.get("ok") is True
    assert game.phase == "attack"
    assert game.current_attacker == 1  # ход перешел игроку!


def test_multiplayer_exit_flow():
    # Игра на 3 игрока: A (1), B (2), C (3)
    game = DurakGame(player_ids=[1, 2, 3])
    game.trump_suit = "♦"
    game.deck = []  # колода пуста
    game.current_attacker = 1
    game.current_defender = 2

    game.hands[1] = [
        {"suit": "♠", "rank": "7"},
        {"suit": "♣", "rank": "K"},  # игрок 1 остается с картой
    ]
    game.hands[2] = [{"suit": "♠", "rank": "8"}]  # последняя карта защитника
    game.hands[3] = [{"suit": "♣", "rank": "10"}]

    game.attack(1, {"suit": "♠", "rank": "7"})
    game.defend(2, {"suit": "♠", "rank": "7"}, {"suit": "♠", "rank": "8"})

    # При пустой колоде защитник сбросил последнюю карту -> авто-отбой!
    # Игрок 2 вышел из игры, новым атакующим должен стать 3, а не 2!
    assert 2 in game.finished_order
    assert game.current_attacker == 3
    assert game.current_defender == 1
    assert game.phase == "attack"


def test_game_over_last_player_loser():
    # 2 игрока сбрасывают карты, остается 1 -> он дурак
    game = DurakGame(player_ids=[1, 2, 3])
    game.trump_suit = "♦"
    game.deck = []
    game.current_attacker = 1
    game.current_defender = 2

    game.hands[1] = [{"suit": "♠", "rank": "7"}]
    game.hands[2] = [{"suit": "♠", "rank": "8"}]
    game.hands[3] = [{"suit": "♣", "rank": "10"}]

    game.attack(1, {"suit": "♠", "rank": "7"})
    game.defend(2, {"suit": "♠", "rank": "7"}, {"suit": "♠", "rank": "8"})

    assert game.phase == "done"
    assert game.loser == 3
    assert game.winner == 1


if __name__ == "__main__":
    test_game_initialization()
    test_attack_and_podkidnoy_rules()
    test_defend_rules_and_trumps()
    test_take_and_refill_order()
    test_pass_bito_and_turn_swap()
    test_bot_attack_and_defend_ai()
    test_multiplayer_exit_flow()
    test_game_over_last_player_loser()
    print("=== ALL DURAK GAMEPLAY TESTS PASSED WITH ZERO ERRORS! ===")
