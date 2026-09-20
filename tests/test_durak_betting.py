"""
Тест проверки механики ставок, выплат и возвратов в игре «Дурак».
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bot.game_durak import DurakGame, Card
from backend.db.session import async_session_factory
from backend.db.models import User
from backend.db.crud.users import get_user_by_tg_id, add_user_coins
from backend.api.routers.durak.state import (
    _durak_rooms,
    _durak_check_settlement,
    _durak_leave_room,
)


async def test_durak_game_phase_completion():
    print("=== [1/3] Testing DurakGame phase completion & no overwrite ===")
    game = DurakGame(player_ids=[1001, 1002], stake=25)

    # Имитируем конец игры: колода пуста
    game.deck = []
    # Игрок 1001 сбросил все карты, игрок 1002 остался с 1 картой
    game.hands[1001] = []
    game.hands[1002] = [{"suit": "♠", "rank": "7"}]
    game.current_attacker = 1001
    game.current_defender = 1002

    # Игрок 1002 берет карты
    game.table = [{"attack": {"suit": "♠", "rank": "7"}, "defend": None}]
    res = game.take(1002)
    assert res.get("ok") is True, f"take failed: {res}"
    assert game.phase == "done", f"Expected phase == 'done', got: {game.phase}"
    assert game.winner == 1001, f"Expected winner == 1001, got: {game.winner}"
    assert game.loser == 1002, f"Expected loser == 1002, got: {game.loser}"
    print("[OK] DurakGame phase 'done' is preserved correctly upon take().")

    # Проверка pass_attack
    game2 = DurakGame(player_ids=[2001, 2002], stake=10)
    game2.deck = []
    game2.hands[2001] = []
    game2.hands[2002] = [{"suit": "♥", "rank": "8"}]
    game2.current_attacker = 2001
    game2.current_defender = 2002
    game2.table = [{"attack": {"suit": "♦", "rank": "6"}, "defend": {"suit": "♦", "rank": "7"}}]
    res2 = game2.pass_attack(2001)
    assert res2.get("ok") is True, f"pass_attack failed: {res2}"
    assert game2.phase == "done", f"Expected phase == 'done', got: {game2.phase}"
    assert game2.winner == 2001, f"Expected winner == 2001, got: {game2.winner}"
    assert game2.loser == 2002, f"Expected loser == 2002, got: {game2.loser}"
    print("[OK] DurakGame phase 'done' is preserved correctly upon pass_attack().")


async def setup_test_users():
    async with async_session_factory() as session:
        for tg_id, name in [(777001, "Durak Tester 1"), (777002, "Durak Tester 2")]:
            u = await get_user_by_tg_id(session, tg_id)
            if not u:
                u = User(
                    tg_id=tg_id,
                    username=f"durak_user_{tg_id}",
                    full_name=name,
                    role="student",
                    coins=100,
                    currency_ecosystem_enabled=True,
                )
                session.add(u)
            else:
                u.coins = 100
                u.currency_ecosystem_enabled = True
        await session.commit()


async def test_bot_game_win_reward():
    print("=== [2/3] Testing Bot game win settlement (+2x stake) ===")
    user_id = 777001
    stake = 25
    room_id = "test_bot_win"

    async with async_session_factory() as session:
        # Списываем ставку
        await add_user_coins(session, user_id, -stake)
        u = await get_user_by_tg_id(session, user_id)
        assert u.coins == 75, f"Expected 75 coins after deduction, got: {u.coins}"

    game = DurakGame(player_ids=[user_id, -1], bot_indices=[-1], stake=stake)
    game.phase = "done"
    game.winner = user_id
    game.loser = -1

    _durak_rooms[room_id] = {
        "game": game,
        "mode": "bot",
        "players": [user_id, -1],
        "stake": stake,
        "settled": False,
        "connections": {},
    }

    await _durak_check_settlement(room_id)

    async with async_session_factory() as session:
        u = await get_user_by_tg_id(session, user_id)
        # Баланс должен стать 75 + 50 = 125
        assert u.coins == 125, f"Expected 125 coins after winning, got: {u.coins}"
    print("[OK] Bot game winning correctly awarded 2x stake (net +25 coins).")


async def test_room_exit_refunds():
    print("=== [3/3] Testing Room Exit & Stake Refunds ===")
    u1, u2 = 777001, 777002

    # Тест 3.1: Выход из неоконченной игры с ботом (возврат ставки)
    async with async_session_factory() as session:
        u = await get_user_by_tg_id(session, u1)
        u.coins = 100
        await session.commit()

    bot_room = "test_bot_refund"
    stake = 30
    async with async_session_factory() as session:
        await add_user_coins(session, u1, -stake)

    _durak_rooms[bot_room] = {
        "game": DurakGame(player_ids=[u1, -1], bot_indices=[-1], stake=stake),
        "mode": "bot",
        "players": [u1, -1],
        "stake": stake,
        "settled": False,
        "connections": {},
    }

    leave_res = await _durak_leave_room(bot_room, u1)
    assert leave_res.get("refunded") is True, f"Expected refunded: True, got: {leave_res}"

    async with async_session_factory() as session:
        u = await get_user_by_tg_id(session, u1)
        assert u.coins == 100, f"Expected 100 coins after bot exit refund, got: {u.coins}"
    print("[OK] Bot game exit correctly refunded stake.")

    # Тест 3.2: Отмена комнаты ожидания создателем (возврат ставки создателю)
    online_room = "test_online_cancel"
    stake = 40
    async with async_session_factory() as session:
        await add_user_coins(session, u1, -stake)
        u = await get_user_by_tg_id(session, u1)
        assert u.coins == 60

    _durak_rooms[online_room] = {
        "game": None,
        "mode": "online",
        "players": [u1],
        "players_count": 2,
        "stake": stake,
        "settled": False,
        "connections": {},
    }

    cancel_res = await _durak_leave_room(online_room, u1)
    assert cancel_res.get("status") == "canceled"
    assert cancel_res.get("refunded") is True

    async with async_session_factory() as session:
        u = await get_user_by_tg_id(session, u1)
        assert u.coins == 100, f"Expected 100 coins after creator cancel, got: {u.coins}"
    print("[OK] Creator cancel in waiting lobby correctly refunded stake.")

    # Тест 3.3: Выход второго участника из комнаты ожидания (возврат ставки второму игроку)
    lobby_room = "test_lobby_leave"
    stake = 50
    async with async_session_factory() as session:
        await add_user_coins(session, u1, -stake)  # u1 = 50
        await add_user_coins(session, u2, -stake)  # u2 = 50

    _durak_rooms[lobby_room] = {
        "game": None,
        "mode": "online",
        "players": [u1, u2],
        "players_count": 3,
        "stake": stake,
        "settled": False,
        "connections": {},
    }

    # u2 выходит
    u2_leave = await _durak_leave_room(lobby_room, u2)
    assert u2_leave.get("status") == "left"
    assert u2_leave.get("refunded") is True

    async with async_session_factory() as session:
        u_2 = await get_user_by_tg_id(session, u2)
        assert u_2.coins == 100, f"Expected u2 to be refunded to 100, got: {u_2.coins}"
        u_1 = await get_user_by_tg_id(session, u1)
        assert u_1.coins == 50, f"Expected u1 still invested at 50, got: {u_1.coins}"

    # Комната осталась, в ней остался только u1
    assert _durak_rooms[lobby_room]["players"] == [u1]
    # Теперь u1 тоже отменяет
    await _durak_leave_room(lobby_room, u1)
    async with async_session_factory() as session:
        u_1 = await get_user_by_tg_id(session, u1)
        assert u_1.coins == 100, f"Expected u1 refunded to 100, got: {u_1.coins}"
    print("[OK] Participant exit from waiting lobby refunded participant and kept creator.")

    # Тест 3.4: Сдача (forfeit) посреди онлайн-игры -> соперник забирает банк
    game_room = "test_online_forfeit"
    stake = 20
    async with async_session_factory() as session:
        await add_user_coins(session, u1, -stake)  # 80
        await add_user_coins(session, u2, -stake)  # 80

    active_game = DurakGame(player_ids=[u1, u2], stake=stake)
    _durak_rooms[game_room] = {
        "game": active_game,
        "mode": "online",
        "players": [u1, u2],
        "stake": stake,
        "settled": False,
        "connections": {},
    }

    # u2 сдается посреди игры
    forfeit_res = await _durak_leave_room(game_room, u2)
    assert forfeit_res.get("status") == "forfeited"

    async with async_session_factory() as session:
        # u1 должен получить весь банк (40 монет): 80 + 40 = 120 монет
        u_1 = await get_user_by_tg_id(session, u1)
        assert u_1.coins == 120, f"Expected u1 to receive entire pot (120), got: {u_1.coins}"
        u_2 = await get_user_by_tg_id(session, u2)
        assert u_2.coins == 80, f"Expected u2 to stay at 80, got: {u_2.coins}"
    print("[OK] Online forfeit correctly awarded full pot to remaining opponent.")


async def main():
    await setup_test_users()
    await test_durak_game_phase_completion()
    await test_bot_game_win_reward()
    await test_room_exit_refunds()
    print("\n[SUCCESS] ALL DURAK BETTING, REWARD AND REFUND TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(main())
