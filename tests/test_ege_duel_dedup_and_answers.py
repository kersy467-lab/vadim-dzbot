"""Tests for zero repetitions in duels and exact answer evaluation."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.rooms_ege import EGEDuelRoom
from backend.ege.words_stress import STRESS_WORDS_FIPI, create_stress_question
from backend.ege.words_vocabulary import VOCABULARY_WORDS_FIPI, create_vocab_question


def test_duel_stress_zero_repetitions_in_regular_round():
    room = EGEDuelRoom("test-dedup-stress", 111, "Player1", 222, "Player2", "ege_stress_duel")
    room.status = "playing"

    seen_words = []
    for _ in range(room.round_size):
        q = room.question_for(111)
        assert q is not None
        seen_words.append(q["word"])
        room.make_move(111, {"answer": 0})

    assert len(seen_words) == 10
    assert len(set(seen_words)) == 10, f"Duplicates found in stress duel: {seen_words}"


def test_duel_vocab_zero_repetitions_in_regular_round():
    room = EGEDuelRoom("test-dedup-vocab", 111, "Player1", 222, "Player2", "ege_vocabulary_duel")
    room.status = "playing"

    seen_words = []
    for _ in range(room.round_size):
        q = room.question_for(111)
        assert q is not None
        seen_words.append(q["word"])
        room.make_move(111, {"answer": "anything"})

    assert len(seen_words) == 10
    assert len(set(seen_words)) == 10, f"Duplicates found in vocab duel: {seen_words}"


def test_duel_zero_repetitions_during_sudden_death():
    room = EGEDuelRoom("test-sudden-dedup", 111, "Player1", 222, "Player2", "ege_stress_duel")
    room.status = "playing"

    # Both answer first 10 questions correctly
    for _ in range(10):
        q1 = room._current_question(111)
        room.make_move(111, {"answer": q1["answer"]})
        q2 = room._current_question(222)
        room.make_move(222, {"answer": q2["answer"]})

    assert room.sudden_round == 1
    assert room.round_size == 11

    # Sudden round 1: both answer correctly
    q1 = room._current_question(111)
    room.make_move(111, {"answer": q1["answer"]})
    q2 = room._current_question(222)
    room.make_move(222, {"answer": q2["answer"]})

    assert room.sudden_round == 2
    assert room.round_size == 12

    deck_words = [q["word"] for q in room.deck]
    assert len(deck_words) == 12
    assert len(set(deck_words)) == 12, "Duplicates in sudden death deck!"


def test_stress_words_fipi_codifier_corrections():
    room = EGEDuelRoom("test-fipi", 111, "Player1", 222, "Player2", "ege_stress_duel")

    # Verify that crucial words like красивее, кухонный, начавший, торты have correct stress
    test_cases = [
        ("красИвее", 4),     # и is index 4
        ("кУхонный", 1),     # у is index 1
        ("начАвший", 3),     # а is index 3
        ("тОрты", 1),        # о is index 1
        ("диспансЕр", 7),    # е is index 7
        ("жалюзИ", 5),       # и is index 5
        ("каталОг", 5),      # о is index 5
        ("квартАл", 5),      # а is index 5
        ("созЫв", 3),        # ы is index 3
        ("цемЕнт", 3),       # е is index 3
    ]
    for word_fipi, expected_idx in test_cases:
        q = create_stress_question(word_fipi)
        assert q["answer"] == expected_idx, f"Wrong target for {word_fipi}: got {q['answer']} vs expected {expected_idx}"
        # Accepts int
        assert room._is_correct(q, expected_idx) is True
        # Accepts string representation of int
        assert room._is_correct(q, str(expected_idx)) is True
        # Rejects wrong index
        assert room._is_correct(q, (expected_idx + 1) % len(word_fipi)) is False
        # Rejects boolean
        assert room._is_correct(q, True) is False


def test_vocab_normalization_e_and_yo_and_spaces():
    room = EGEDuelRoom("test-vocab-yo", 111, "Player1", 222, "Player2", "ege_vocabulary_duel")
    q = create_vocab_question("дирижёр")

    # Exact match
    assert room._is_correct(q, "дирижёр") is True
    # With 'е' instead of 'ё'
    assert room._is_correct(q, "дирижер") is True
    # Uppercase
    assert room._is_correct(q, "ДИРИЖЕР") is True
    assert room._is_correct(q, "Дирижёр") is True
    # Surrounding and internal whitespace
    assert room._is_correct(q, "  дирижер   ") is True
    assert room._is_correct(q, "дири жер") is True


def test_both_players_receive_identical_deck_fair_duel():
    room = EGEDuelRoom("test-fair", 111, "Player1", 222, "Player2", "ege_stress_duel")
    room.status = "playing"

    p1_words = []
    p2_words = []
    for _ in range(10):
        q1 = room.question_for(111)
        p1_words.append(q1["word"])
        room.make_move(111, {"answer": 0})

    for _ in range(10):
        q2 = room.question_for(222)
        p2_words.append(q2["word"])
        room.make_move(222, {"answer": 0})

    assert p1_words == p2_words, "Duel questions must be identical for both competitors!"


if __name__ == "__main__":
    test_duel_stress_zero_repetitions_in_regular_round()
    test_duel_vocab_zero_repetitions_in_regular_round()
    test_duel_zero_repetitions_during_sudden_death()
    test_stress_words_fipi_codifier_corrections()
    test_vocab_normalization_e_and_yo_and_spaces()
    test_both_players_receive_identical_deck_fair_duel()
    print("ALL DEDUPLICATION AND ANSWER VALIDATION TESTS PASSED!")
