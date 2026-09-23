# backend/api/rooms_checkers/ai.py
"""ИИ-движок для игры в русские шашки (Minimax с Alpha-Beta отсечением)."""
import random
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Heuristic weights for Russian Checkers
MAN_VALUE = 100
KING_VALUE = 320

CENTER_SQUARES = {
    (3, 2), (3, 4), (4, 3), (4, 5),  # center
    (2, 3), (2, 5), (5, 2), (5, 4)   # extended center
}

MAIN_DIAGONAL_SQUARES = {
    (0, 7), (1, 6), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (7, 0)
}


def evaluate_board(board, bot_color: str) -> int:
    """Оценивает позицию на доске с точки зрения bot_color."""
    score = 0
    w_moves = 0
    b_moves = 0

    for r in range(8):
        for c in range(8):
            p = board.board[r][c]
            if not p:
                continue

            is_white = p in ('w', 'W')
            is_king = p in ('W', 'B')
            side_mult = 1 if is_white else -1

            val = KING_VALUE if is_king else MAN_VALUE

            # Positional bonuses
            if not is_king:
                # Rank advancement toward coronation
                advancement = (7 - r) if is_white else r
                val += advancement * 6

                # Home row protection (prevents enemy coronation)
                if is_white and r == 7:
                    val += 18
                elif not is_white and r == 0:
                    val += 18

                # Penalty for edge columns (less mobility)
                if c == 0 or c == 7:
                    val -= 6
            else:
                # King central & diagonal control
                if (r, c) in MAIN_DIAGONAL_SQUARES:
                    val += 16
                elif (r, c) in CENTER_SQUARES:
                    val += 12

            # Center square control for all pieces
            if (r, c) in CENTER_SQUARES:
                val += 10

            score += val * side_mult

    # Mobility bonus
    if board.turn == "white":
        w_moves = len(board.get_legal_moves())
    else:
        b_moves = len(board.get_legal_moves())

    mobility_delta = (w_moves - b_moves) * 4
    score += mobility_delta

    return score if bot_color == "white" else -score


def minimax(
    board,
    depth: int,
    alpha: float,
    beta: float,
    is_maximizing: bool,
    bot_color: str
) -> float:
    """Алгоритм Minimax с Alpha-Beta отсечением для русских шашек."""
    if depth <= 0 or board.is_game_over():
        winner = board.get_winner()
        if winner == bot_color:
            return 100000.0 + depth
        elif winner is not None:
            return -100000.0 - depth
        return float(evaluate_board(board, bot_color))

    legal_moves = board.get_legal_moves()
    if not legal_moves:
        current_is_bot = (board.turn == bot_color)
        if current_is_bot == is_maximizing:
            return -100000.0 - depth
        else:
            return 100000.0 + depth

    if is_maximizing:
        max_eval = -float('inf')
        for move in legal_moves:
            sim_board = board.clone()
            ok, res = sim_board.push_move(move)
            if not ok:
                continue
            next_is_max = (sim_board.turn == bot_color)
            next_depth = depth if res == "continue" else depth - 1
            val = minimax(sim_board, next_depth, alpha, beta, next_is_max, bot_color)
            if val > max_eval:
                max_eval = val
            if max_eval > alpha:
                alpha = max_eval
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float('inf')
        for move in legal_moves:
            sim_board = board.clone()
            ok, res = sim_board.push_move(move)
            if not ok:
                continue
            next_is_max = (sim_board.turn == bot_color)
            next_depth = depth if res == "continue" else depth - 1
            val = minimax(sim_board, next_depth, alpha, beta, next_is_max, bot_color)
            if val < min_eval:
                min_eval = val
            if min_eval < beta:
                beta = min_eval
            if beta <= alpha:
                break
        return min_eval


def get_best_checkers_move(
    board,
    depth: int = 3,
    bot_color: str = "black"
) -> Optional[str]:
    """Вычисляет лучший ход для бота в текущей позиции."""
    legal_moves = board.get_legal_moves()
    if not legal_moves:
        return None
    if len(legal_moves) == 1:
        return legal_moves[0]

    best_score = -float('inf')
    best_moves: List[str] = []

    for move in legal_moves:
        sim_board = board.clone()
        ok, res = sim_board.push_move(move)
        if not ok:
            continue

        next_is_max = (sim_board.turn == bot_color)
        next_depth = depth if res == "continue" else depth - 1
        score = minimax(
            sim_board,
            next_depth,
            -float('inf'),
            float('inf'),
            next_is_max,
            bot_color
        )

        if score > best_score + 1.0:
            best_score = score
            best_moves = [move]
        elif abs(score - best_score) <= 1.0:
            best_moves.append(move)

    if not best_moves:
        return random.choice(legal_moves)

    return random.choice(best_moves)
