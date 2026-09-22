import logging
from typing import Optional, List, Tuple
import chess

logger = logging.getLogger(__name__)

# Piece material values in centipawns
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

# Simplified Piece-Square Tables (White perspective, square 0=A1 .. 63=H8)
PST_PAWN = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
]

PST_KNIGHT = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]

PST_BISHOP = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]

PST_ROOK = [
      0,  0,  0,  0,  0,  0,  0,  0,
      5, 10, 10, 10, 10, 10, 10,  5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
      0,  0,  0,  5,  5,  0,  0,  0
]

PST_QUEEN = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
]

PST_KING_MIDGAME = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20
]

PST_MAP = {
    chess.PAWN: PST_PAWN,
    chess.KNIGHT: PST_KNIGHT,
    chess.BISHOP: PST_BISHOP,
    chess.ROOK: PST_ROOK,
    chess.QUEEN: PST_QUEEN,
    chess.KING: PST_KING_MIDGAME,
}

def get_position_key(board: chess.Board) -> str:
    """Returns unique position key (board fen + turn + castling rights)."""
    return f"{board.board_fen()} {'w' if board.turn == chess.WHITE else 'b'} {board.castling_rights}"

def evaluate_board(board: chess.Board, bot_color: chess.Color, depth: int = 0) -> int:
    """Evaluates the board from the bot's perspective in centipawns."""
    if board.is_checkmate():
        mate_score = 900000 + depth * 1000
        return -mate_score if board.turn == bot_color else mate_score
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves():
        return 0

    score = 0
    for sq, piece in board.piece_map().items():
        val = PIECE_VALUES.get(piece.piece_type, 0)
        pst = PST_MAP.get(piece.piece_type)
        pst_sq = sq if piece.color == chess.WHITE else chess.square_mirror(sq)
        pst_val = pst[pst_sq] if pst else 0

        total_piece_val = val + pst_val
        if piece.color == chess.WHITE:
            score += total_piece_val
        else:
            score -= total_piece_val

    # Mobility bonus
    mobility = len(list(board.legal_moves))
    if board.turn == chess.WHITE:
        score += mobility * 3
    else:
        score -= mobility * 3

    # Check bonus
    if board.is_check():
        if board.turn == chess.WHITE:
            score -= 35
        else:
            score += 35

    return score if bot_color == chess.WHITE else -score

def order_moves(board: chess.Board, moves: List[chess.Move]) -> List[chess.Move]:
    """Orders moves for maximum alpha-beta cutoffs (MVV-LVA, promotions, checks)."""
    scored = []
    for move in moves:
        prio = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            v_val = PIECE_VALUES.get(victim.piece_type, 100) if victim else 100
            a_val = PIECE_VALUES.get(attacker.piece_type, 100) if attacker else 100
            prio += 10000 + (v_val * 10 - a_val)
        if move.promotion:
            promo_val = PIECE_VALUES.get(move.promotion, 900)
            prio += 8000 + promo_val
        if board.gives_check(move):
            prio += 1500
        scored.append((prio, move))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]

def alpha_beta(
    board: chess.Board,
    depth: int,
    alpha: float,
    beta: float,
    is_maximizing: bool,
    bot_color: chess.Color
) -> float:
    """Minimax search with Alpha-Beta pruning."""
    if depth == 0 or board.is_game_over():
        return evaluate_board(board, bot_color, depth=depth)

    legal_moves = order_moves(board, list(board.legal_moves))
    if not legal_moves:
        return evaluate_board(board, bot_color, depth=depth)

    if is_maximizing:
        max_eval = -float("inf")
        for move in legal_moves:
            board.push(move)
            eval_score = alpha_beta(board, depth - 1, alpha, beta, False, bot_color)
            board.pop()
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float("inf")
        for move in legal_moves:
            board.push(move)
            eval_score = alpha_beta(board, depth - 1, alpha, beta, True, bot_color)
            board.pop()
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval

def get_best_bot_move(
    board: chess.Board,
    depth: int = 3,
    bot_color: Optional[chess.Color] = None,
    position_history: Optional[List[str]] = None
) -> Optional[chess.Move]:
    """
    Finds the optimal chess move using Minimax with Alpha-Beta pruning at depth 3,
    complete with anti-loop and repetition protection.
    """
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    if bot_color is None:
        bot_color = board.turn

    history_set = set(position_history or [])
    ordered_moves = order_moves(board, legal_moves)

    # Track recent move reversal (oscillating piece)
    prev_from = None
    prev_to = None
    if len(board.move_stack) >= 2:
        last_bot_move = board.move_stack[-2]
        prev_from = last_bot_move.from_square
        prev_to = last_bot_move.to_square

    best_move = None
    best_score = -float("inf")
    alpha = -float("inf")
    beta = float("inf")

    # Current static evaluation to determine if bot is winning/losing
    current_eval = evaluate_board(board, bot_color)

    for move in ordered_moves:
        board.push(move)

        if board.is_checkmate():
            board.pop()
            return move

        # 1. Evaluate subtree with Alpha-Beta
        score = alpha_beta(board, depth - 1, alpha, beta, False, bot_color)

        # 2. ANTI-LOOP & REPETITION PROTECTION
        # Check if this move triggers board-level repetition
        rep_count = 2 if board.is_repetition(2) else (3 if board.is_repetition(3) else 1)
        next_key = get_position_key(board)

        # Repetition penalty logic:
        if rep_count >= 2 or next_key in history_set:
            if current_eval > 80:
                # Winning: severely penalize draw by repetition
                score -= 800
            elif current_eval >= -150:
                # Equal/playable: actively avoid looping back and forth
                score -= 400
            # If hopelessly losing (current_eval < -200), repetition is acceptable as a drawing tactic

        # 3. Oscillation penalty: moving piece right back to where it was 1 turn ago
        if prev_from is not None and prev_to is not None:
            if move.from_square == prev_to and move.to_square == prev_from:
                if not board.is_check() and not board.is_capture(move):
                    score -= 220  # Strong penalty for back-and-forth oscillation

        # 4. Progressive bonus (slight preference for pawn advances and center activity for normal moves)
        if abs(score) < 80000:
            piece = board.piece_at(move.to_square)
            if piece and piece.piece_type == chess.PAWN:
                score += 6
            elif piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                score += 3

        board.pop()

        if score > best_score:
            best_score = score
            best_move = move

        alpha = max(alpha, best_score)

    return best_move or ordered_moves[0]
