from backend.api.rooms_ege import EGEDuelRoom


def test_duel_server_validates_the_answer_instead_of_client_flag():
    room = EGEDuelRoom("ege-test", 101, "Первый", 202, "Второй", "ege_vocabulary_duel")
    room.status = "playing"
    task = room.question_for(101)
    assert "answer" not in task

    ok, _ = room.make_move(101, {"answer": "совершенно другое слово"})

    assert ok is True
    assert room.answers[101] == [False]
    assert room.question_for(101)["id"] != task["id"]


def test_duel_accepts_independent_answers_and_rejects_client_correct_flag():
    room = EGEDuelRoom("ege-test", 101, "Первый", 202, "Второй", "ege_stress_duel")
    room.status = "playing"

    ok, message = room.make_move(101, {"correct": True})

    assert ok is False
    assert "ответ" in message.lower()

    for _ in range(3):
        expected_answer = room._current_question(101)["answer"]
        ok, _ = room.make_move(101, {"answer": expected_answer})
        assert ok is True
    assert len(room.answers[101]) == 3
    assert len(room.answers[202]) == 0


def test_random_answers_do_not_trigger_sudden_death():
    room = EGEDuelRoom("ege-test", 101, "Первый", 202, "Второй", "ege_vocabulary_duel")
    room.status = "playing"

    for _ in range(10):
        assert room.make_move(101, {"answer": "неверно"})[0]
        assert room.make_move(202, {"answer": "неверно"})[0]

    assert room.status == "finished"
    assert room.sudden_round == 0


def test_perfect_sudden_death_continues_until_someone_makes_an_error():
    room = EGEDuelRoom("ege-test", 101, "Первый", 202, "Второй", "ege_stress_duel")
    room.status = "playing"

    for _ in range(10):
        assert room.make_move(101, {"answer": room._current_question(101)["answer"]})[0]
        assert room.make_move(202, {"answer": room._current_question(202)["answer"]})[0]
    assert room.sudden_round == 1
    assert room.status == "playing"

    assert room.make_move(101, {"answer": room._current_question(101)["answer"]})[0]
    assert room.make_move(202, {"answer": room._current_question(202)["answer"]})[0]
    assert room.sudden_round == 2
    assert room.status == "playing"
