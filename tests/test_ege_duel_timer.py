"""Unit tests for EGEDuelRoom timers (35s main round, 5s sudden death)."""
import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.api.rooms_ege import EGEDuelRoom, MAIN_ROUND_TIME_LIMIT, SUDDEN_WORD_TIME_LIMIT


def test_ege_duel_timer_initialization():
    room = EGEDuelRoom(
        room_id="test_room_1",
        host_tg_id=1001,
        host_name="HostPlayer",
        opponent_tg_id=1002,
        opponent_name="OpponentPlayer",
        game_type="ege_stress_duel",
    )
    assert room.status == "waiting"
    assert room.round_size == 10
    assert room.sudden_round == 0
    assert len(room.player_started_at) == 0

    # Before playing, time remaining is 0
    assert room.get_time_remaining(1001) == 0.0


def test_ege_duel_timer_start_and_countdown():
    room = EGEDuelRoom("test_room_2", 1001, "Host", 1002, "Opponent")
    room.status = "playing"

    # Host views room
    d_host = room.to_dict(1001)
    assert d_host["timer_limit"] == 35.0
    assert d_host["timer_mode"] == "main"
    assert 34.0 <= d_host["time_remaining"] <= 35.0
    assert 1001 in room.player_started_at

    # Opponent hasn't viewed yet, not in player_started_at
    assert 1002 not in room.player_started_at

    # Opponent views room
    d_opp = room.to_dict(1002)
    assert 1002 in room.player_started_at
    assert 34.0 <= d_opp["time_remaining"] <= 35.0


def test_ege_duel_main_round_timeout():
    room = EGEDuelRoom("test_room_3", 1001, "Host", 1002, "Opponent")
    room.status = "playing"

    # Host answers 3 questions correctly
    q1 = room.question_for(1001)
    ans1 = room.deck[0]["answer"]
    ok, _ = room.make_move(1001, {"answer": ans1})
    assert ok is True

    q2 = room.question_for(1001)
    ans2 = room.deck[1]["answer"]
    room.make_move(1001, {"answer": ans2})

    assert len(room.answers[1001]) == 2

    # Simulate 37 seconds elapsed for host (35-second limit plus server grace)
    room.player_started_at[1001] = time.time() - 37.0

    # Check timeout via to_dict
    d = room.to_dict(1001)
    assert d["your_finished"] is True
    assert room.status == "finished"
    assert room.winner == 1002
    assert len(room.answers[1001]) == 10
    # 2 answered, 8 timed out as False
    assert room.answers[1001] == [True, True, False, False, False, False, False, False, False, False]
    assert d["your_errors"] == 8
    assert d["your_score"] == 2


def test_ege_duel_client_timeout_message():
    room = EGEDuelRoom("test_room_4", 1001, "Host", 1002, "Opponent")
    room.status = "playing"

    # Host answers 1 question, then client sends __timeout__
    ans1 = room.deck[0]["answer"]
    room.make_move(1001, {"answer": ans1})

    ok, msg = room.make_move(1001, {"answer": "__timeout__"})
    assert ok is True
    assert len(room.answers[1001]) == 10
    assert room.answers[1001] == [True] + [False] * 9


def test_ege_duel_sudden_death_5s_timer():
    room = EGEDuelRoom("test_room_5", 1001, "Host", 1002, "Opponent")
    room.status = "playing"

    # Both players get 10 correct answers in main round
    for i in range(10):
        ans = room.deck[i]["answer"]
        room.make_move(1001, {"answer": ans})
        room.make_move(1002, {"answer": ans})

    # Tied 10:10 with 0 errors -> enters Sudden Death round 1!
    assert room.sudden_round == 1
    assert room.round_size == 11
    assert room.status == "playing"

    # Host views sudden death question
    d_host = room.to_dict(1001)
    assert d_host["is_sudden_death"] is True
    assert d_host["timer_limit"] == 5.0
    assert d_host["timer_mode"] == "sudden"
    assert 4.0 <= d_host["time_remaining"] <= 5.0

    # Host answers correctly
    sudden_q = room.deck[10]
    ok, _ = room.make_move(1001, {"answer": sudden_q["answer"]})
    assert ok is True
    assert len(room.answers[1001]) == 11
    assert room.answers[1001][-1] is True

    # Opponent times out on the sudden death word (e.g. 6s elapsed)
    room.to_dict(1002)
    room.sudden_question_started_at[(1002, 1)] = time.time() - 6.5

    d_opp = room.to_dict(1002)
    # Opponent timed out -> marked False -> duel finished!
    assert room.status == "finished"
    assert room.winner == 1001
    assert d_host["result"] == "win" or room.winner == 1001


def test_ege_duel_rematch_resets_timers():
    room = EGEDuelRoom("test_room_6", 1001, "Host", 1002, "Opponent")
    room.status = "finished"
    room.player_started_at[1001] = 12345.0
    room.sudden_question_started_at[(1001, 1)] = 12345.0

    ok, _ = room.request_rematch(1001)
    assert ok is True
    ok, _ = room.request_rematch(1002)
    assert ok is True
    assert room.status == "playing"
    assert len(room.player_started_at) == 0
    assert len(room.sudden_question_started_at) == 0


def test_ege_vocab_duel_timer_and_empty_protection():
    room = EGEDuelRoom("test_room_vocab", 1001, "Host", 1002, "Opponent", game_type="ege_vocabulary_duel")
    room.status = "playing"

    # Vocab duel main round limit should be 70s
    d = room.to_dict(1001)
    assert d["timer_limit"] == 70.0
    assert 69.0 <= d["time_remaining"] <= 70.0

    # Sending empty string or whitespace must be rejected and not burn a question
    ok, msg = room.make_move(1001, {"answer": ""})
    assert ok is False
    assert "Введите ответ" in msg
    assert len(room.answers[1001]) == 0

    ok, msg = room.make_move(1001, {"answer": "   "})
    assert ok is False
    assert len(room.answers[1001]) == 0

    # If room is finished, make_move must return True gracefully
    room.status = "finished"
    ok, msg = room.make_move(1001, {"answer": "палисадник"})
    assert ok is True
    assert "завершена" in msg


if __name__ == "__main__":
    test_ege_duel_timer_initialization()
    test_ege_duel_timer_start_and_countdown()
    test_ege_duel_main_round_timeout()
    test_ege_duel_client_timeout_message()
    test_ege_duel_sudden_death_5s_timer()
    test_ege_duel_rematch_resets_timers()
    test_ege_vocab_duel_timer_and_empty_protection()
    print("All EGE duel timer tests passed successfully!")

