import os
import sys
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.rooms_ege import EGEDuelRoom
from backend.ege.ranking import clamp_rating, medal_for_rating, settle_duel


def _correct(room: EGEDuelRoom, tg_id: int):
    return room.make_move(tg_id, {"answer": room._current_question(tg_id)["answer"]})


def _wrong(room: EGEDuelRoom, tg_id: int):
    question = room._current_question(tg_id)
    answer = "__definitely_wrong__" if question["mode"] == "vocabulary" else -1
    return room.make_move(tg_id, {"answer": answer})


def _room(game_type: str = "ege_stress_duel") -> EGEDuelRoom:
    room = EGEDuelRoom("ege-test", 101, "Первый", 202, "Второй", game_type)
    room.status = "playing"
    return room


def test_duel_server_validates_answer_and_hides_answer_from_client():
    room = _room("ege_vocabulary_duel")
    task = room.question_for(101)
    assert "answer" not in task

    ok, _ = room.make_move(101, {"answer": "совершенно другое слово"})

    assert ok is True
    assert room.answers[101] == [False]
    assert room.question_for(101)["id"] != task["id"]


def test_duel_rejects_client_correct_flag_and_allows_independent_progress():
    room = _room()

    ok, message = room.make_move(101, {"correct": True})
    assert ok is False
    assert "ответ" in message.lower()

    for _ in range(3):
        assert _correct(room, 101)[0]
    assert len(room.answers[101]) == 3
    assert len(room.answers[202]) == 0


def test_first_finisher_waits_and_is_not_declared_winner():
    room = _room("ege_vocabulary_duel")
    for _ in range(10):
        assert _wrong(room, 101)[0]

    state = room.to_dict(viewer_tg_id=101)
    assert room.status == "playing"
    assert room.winner is None
    assert state["result"] is None
    assert state["your_finished"] is True
    assert state["opponent_finished"] is False
    assert state["your_errors"] == 10
    assert state["question"] is None


def test_first_finisher_can_later_lose():
    room = _room()
    for _ in range(10):
        assert _wrong(room, 101)[0]
    assert room.status == "playing"

    for _ in range(10):
        assert _correct(room, 202)[0]

    first = room.to_dict(viewer_tg_id=101)
    second = room.to_dict(viewer_tg_id=202)
    assert room.status == "finished"
    assert room.winner == 202
    assert first["result"] == "loss"
    assert second["result"] == "win"
    assert first["your_errors"] == 10
    assert first["opponent_errors"] == 0
    assert second["your_errors"] == 0
    assert second["opponent_errors"] == 10


def test_equal_scores_trigger_sudden_death_until_decisive_winner_and_no_draw():
    room = _room()
    for _ in range(10):
        assert _correct(room, 101)[0]
        assert _correct(room, 202)[0]

    # Равный счёт после 10 вопросов: ничьей нет, начинается Внезапная смерть!
    assert room.status == "playing"
    assert room.winner is None
    assert room.sudden_round == 1
    assert room.round_size == 11

    state = room.to_dict(viewer_tg_id=101)
    assert state["result"] is None
    assert state["is_sudden_death"] is True
    assert state["sudden_round"] == 1
    assert state["round_size"] == 11
    assert state["your_finished"] is False
    assert state["question"] is not None

    # Дополнительный раунд 1: оба снова отвечают верно -> раунд 2 внезапной смерти
    assert _correct(room, 101)[0]
    assert _correct(room, 202)[0]
    assert room.status == "playing"
    assert room.sudden_round == 2
    assert room.round_size == 12

    # Дополнительный раунд 2: 101 отвечает верно, 202 ошибается -> 101 побеждает!
    assert _correct(room, 101)[0]
    assert _wrong(room, 202)[0]

    assert room.status == "finished"
    assert room.winner == 101
    final_101 = room.to_dict(viewer_tg_id=101)
    final_202 = room.to_dict(viewer_tg_id=202)
    assert final_101["result"] == "win"
    assert final_202["result"] == "loss"
    assert final_101["your_errors"] == 0
    assert final_101["opponent_errors"] == 1

    # Проверяем сброс round_size и sudden_round при реванше
    assert room.request_rematch(101)[0]
    assert room.request_rematch(202)[0]
    assert room.status == "playing"
    assert room.round_size == 10
    assert room.sudden_round == 0


def test_duel_result_exposes_winner_score_and_personal_errors():
    room = _room()
    for idx in range(10):
        assert _correct(room, 101)[0]
        assert (_wrong(room, 202) if idx < 2 else _correct(room, 202))[0]

    winner_state = room.to_dict(viewer_tg_id=101)
    loser_state = room.to_dict(viewer_tg_id=202)
    assert room.status == "finished"
    assert winner_state["winner"] == 101
    assert winner_state["winner_name"] == "Первый"
    assert winner_state["result"] == "win"
    assert loser_state["result"] == "loss"
    assert (winner_state["your_score"], winner_state["opponent_score"]) == (10, 8)
    assert (winner_state["your_errors"], winner_state["opponent_errors"]) == (0, 2)
    assert (loser_state["your_errors"], loser_state["opponent_errors"]) == (2, 0)


def test_ege_medal_boundaries_special_titan_and_rating_clamp():
    assert clamp_rating(-25) == 0
    assert clamp_rating(1030) == 1000
    expected = [
        (0, "Рекрут"), (100, "Страж"), (200, "Рыцарь"), (300, "Герой"),
        (400, "Легенда"), (500, "Властелин"), (600, "Божество"), (800, "Титан"),
    ]
    for rating, medal in expected:
        assert medal_for_rating(rating)["name"] == medal

    assert medal_for_rating(900, 1)["display_name"] == "Титан (1)"
    assert medal_for_rating(900, 5)["image_key"] == "titan_top_5"
    assert medal_for_rating(900, 6)["display_name"] == "Титан"
    assert medal_for_rating(799, 1)["display_name"] == "Божество"


def test_rating_and_wld_are_settled_once_even_for_concurrent_calls():
    room = _room()
    room.status = "finished"
    room.winner = 101
    users = {
        101: SimpleNamespace(ege_rating=990, ege_wins=4, ege_losses=1, ege_draws=0),
        202: SimpleNamespace(ege_rating=10, ege_wins=1, ege_losses=4, ege_draws=0),
    }
    session = SimpleNamespace(commit=AsyncMock())

    async def run():
        with patch("backend.ege.ranking._users_by_tg_ids", AsyncMock(return_value=users)):
            await asyncio.gather(settle_duel(session, room), settle_duel(session, room))
            await settle_duel(session, room)

    asyncio.run(run())
    assert users[101].ege_rating == 1000
    assert users[202].ege_rating == 0
    assert users[101].ege_wins == 5
    assert users[202].ege_losses == 5
    assert room.rating_changes == {101: 10, 202: -10}
    assert session.commit.await_count == 1


def test_draw_updates_only_draw_counter_and_no_mmr():
    room = _room()
    room.status = "finished"
    room.winner = None
    users = {
        101: SimpleNamespace(ege_rating=500, ege_wins=2, ege_losses=3, ege_draws=4),
        202: SimpleNamespace(ege_rating=600, ege_wins=3, ege_losses=2, ege_draws=4),
    }
    session = SimpleNamespace(commit=AsyncMock())

    async def run():
        with patch("backend.ege.ranking._users_by_tg_ids", AsyncMock(return_value=users)):
            await settle_duel(session, room)

    asyncio.run(run())
    assert users[101].ege_rating == 500
    assert users[202].ege_rating == 600
    assert users[101].ege_draws == 5
    assert users[202].ege_draws == 5
    assert room.rating_changes == {101: 0, 202: 0}
    assert session.commit.await_count == 1
