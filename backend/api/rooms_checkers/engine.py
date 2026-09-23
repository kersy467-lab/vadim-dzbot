# backend/api/rooms_checkers/engine.py
"""Движок классических русских шашек 8x8."""
from typing import List, Tuple, Optional, Dict, Set

FILES = "abcdefgh"

class CheckersBoard:
    def __init__(self):
        self.board: List[List[Optional[str]]] = [[None] * 8 for _ in range(8)]
        self.turn: str = "white"  # 'white' | 'black'
        self.active_jump_piece: Optional[str] = None  # e.g. "e5" if in multi-jump
        self.captured_in_turn: List[Tuple[int, int]] = []
        self.move_history: List[str] = []
        self.reset()

    def reset(self):
        self.board = [[None] * 8 for _ in range(8)]
        self.turn = "white"
        self.active_jump_piece = None
        self.captured_in_turn = []
        self.move_history = []

        # Black pieces on ranks 8, 7, 6 (r = 0, 1, 2)
        for r in range(3):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.board[r][c] = 'b'

        # White pieces on ranks 3, 2, 1 (r = 5, 6, 7)
        for r in range(5, 8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.board[r][c] = 'w'

    @staticmethod
    def rc_to_sq(r: int, c: int) -> str:
        return f"{FILES[c]}{8 - r}"

    @staticmethod
    def sq_to_rc(sq: str) -> Tuple[int, int]:
        c = FILES.index(sq[0].lower())
        r = 8 - int(sq[1])
        return r, c

    @staticmethod
    def is_valid_sq(r: int, c: int) -> bool:
        return 0 <= r < 8 and 0 <= c < 8 and (r + c) % 2 == 1

    def to_fen(self) -> str:
        rows = []
        for r in range(8):
            row_str = "".join(self.board[r][c] if self.board[r][c] else "." for c in range(8))
            rows.append(row_str)
        t = "w" if self.turn == "white" else "b"
        jump = self.active_jump_piece or "-"
        return f"{'/'.join(rows)} {t} {jump}"

    def load_fen(self, fen: str):
        parts = fen.strip().split()
        rows = parts[0].split("/")
        self.board = [[None] * 8 for _ in range(8)]
        for r in range(8):
            for c in range(8):
                ch = rows[r][c]
                self.board[r][c] = ch if ch in "wbWB" else None
        self.turn = "white" if len(parts) > 1 and parts[1] == "w" else "black"
        self.active_jump_piece = parts[2] if len(parts) > 2 and parts[2] != "-" else None
        self.captured_in_turn = []

    def get_piece_captures(self, r: int, c: int) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        piece = self.board[r][c]
        if not piece:
            return []
        is_white = piece in ('w', 'W')
        is_king = piece in ('W', 'B')
        enemy_chars = ('b', 'B') if is_white else ('w', 'W')
        captures = []
        dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

        if not is_king:
            for dr, dc in dirs:
                mid_r, mid_c = r + dr, c + dc
                to_r, to_c = r + 2 * dr, c + 2 * dc
                if self.is_valid_sq(to_r, to_c) and self.board[to_r][to_c] is None:
                    if (mid_r, mid_c) not in self.captured_in_turn:
                        if self.board[mid_r][mid_c] in enemy_chars:
                            captures.append(((to_r, to_c), (mid_r, mid_c)))
        else:
            for dr, dc in dirs:
                mid_piece = None
                mid_pos = None
                for dist in range(1, 8):
                    curr_r, curr_c = r + dist * dr, c + dist * dc
                    if not self.is_valid_sq(curr_r, curr_c):
                        break
                    p = self.board[curr_r][curr_c]
                    if p is not None:
                        if mid_piece is not None:
                            break  # cannot jump two pieces
                        if (curr_r, curr_c) in self.captured_in_turn or p not in enemy_chars:
                            break  # friendly piece or already captured
                        mid_piece = p
                        mid_pos = (curr_r, curr_c)
                    elif mid_piece is not None:
                        captures.append(((curr_r, curr_c), mid_pos))
        return captures

    def get_piece_non_captures(self, r: int, c: int) -> List[Tuple[int, int]]:
        piece = self.board[r][c]
        if not piece:
            return []
        is_white = piece in ('w', 'W')
        is_king = piece in ('W', 'B')
        moves = []

        if not is_king:
            forward_dr = -1 if is_white else 1
            for dc in (-1, 1):
                to_r, to_c = r + forward_dr, c + dc
                if self.is_valid_sq(to_r, to_c) and self.board[to_r][to_c] is None:
                    moves.append((to_r, to_c))
        else:
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                for dist in range(1, 8):
                    to_r, to_c = r + dist * dr, c + dist * dc
                    if not self.is_valid_sq(to_r, to_c) or self.board[to_r][to_c] is not None:
                        break
                    moves.append((to_r, to_c))
        return moves

    def has_captures(self, color: str) -> bool:
        player_chars = ('w', 'W') if color == "white" else ('b', 'B')
        for r in range(8):
            for c in range(8):
                if self.board[r][c] in player_chars:
                    if len(self.get_piece_captures(r, c)) > 0:
                        return True
        return False

    def get_legal_moves(self) -> List[str]:
        if self.active_jump_piece:
            r, c = self.sq_to_rc(self.active_jump_piece)
            caps = self.get_piece_captures(r, c)
            from_sq = self.active_jump_piece
            return [f"{from_sq}{self.rc_to_sq(to_r, to_c)}" for (to_r, to_c), _ in caps]

        player_chars = ('w', 'W') if self.turn == "white" else ('b', 'B')
        must_capture = self.has_captures(self.turn)
        legal = []

        for r in range(8):
            for c in range(8):
                if self.board[r][c] in player_chars:
                    from_sq = self.rc_to_sq(r, c)
                    if must_capture:
                        for (to_r, to_c), _ in self.get_piece_captures(r, c):
                            legal.append(f"{from_sq}{self.rc_to_sq(to_r, to_c)}")
                    else:
                        for to_r, to_c in self.get_piece_non_captures(r, c):
                            legal.append(f"{from_sq}{self.rc_to_sq(to_r, to_c)}")
        return legal

    def push_step(self, from_sq: str, to_sq: str) -> Tuple[bool, str]:
        from_sq, to_sq = from_sq.lower().strip(), to_sq.lower().strip()
        move_str = f"{from_sq}{to_sq}"
        legal = self.get_legal_moves()
        if move_str not in legal:
            if self.has_captures(self.turn) and not self.active_jump_piece:
                return False, "Взятие обязательно по правилам шашек"
            return False, "Недопустимый ход"

        fr_r, fr_c = self.sq_to_rc(from_sq)
        to_r, to_c = self.sq_to_rc(to_sq)
        piece = self.board[fr_r][fr_c]
        captures = self.get_piece_captures(fr_r, fr_c)
        matching_cap = next((c for c in captures if c[0] == (to_r, to_c)), None)

        self.board[fr_r][fr_c] = None
        self.board[to_r][to_c] = piece

        if matching_cap:
            _, cap_pos = matching_cap
            self.captured_in_turn.append(cap_pos)

            # Promotion on the fly during capture
            if piece == 'w' and to_r == 0:
                self.board[to_r][to_c] = 'W'
            elif piece == 'b' and to_r == 7:
                self.board[to_r][to_c] = 'B'

            more_caps = self.get_piece_captures(to_r, to_c)
            if more_caps:
                self.active_jump_piece = to_sq
                return True, "continue"

            # Remove all captured pieces
            for cr, cc in self.captured_in_turn:
                self.board[cr][cc] = None
            self.captured_in_turn = []
            self.active_jump_piece = None
        else:
            if piece == 'w' and to_r == 0:
                self.board[to_r][to_c] = 'W'
            elif piece == 'b' and to_r == 7:
                self.board[to_r][to_c] = 'B'

        self.move_history.append(move_str)
        self.turn = "black" if self.turn == "white" else "white"
        return True, "done"

    def push_move(self, move_val: str) -> Tuple[bool, str]:
        s = str(move_val).strip().lower().replace("-", "").replace(":", "").replace(" ", "")
        if len(s) < 4 or len(s) % 2 != 0:
            return False, f"Некорректный формат хода: {move_val}"

        steps = [s[i:i+4] for i in range(0, len(s) - 2, 2)]
        for i, step in enumerate(steps):
            f_sq, t_sq = step[:2], step[2:4]
            ok, res = self.push_step(f_sq, t_sq)
            if not ok:
                return False, res
            if res == "done" and i < len(steps) - 1:
                return False, "Ход завершился раньше конца переданной последовательности"
            if res == "continue" and i == len(steps) - 1:
                return True, "continue"
        return True, "done"

    def is_game_over(self) -> bool:
        return len(self.get_legal_moves()) == 0

    def get_winner(self) -> Optional[str]:
        if not self.is_game_over():
            return None
        return "black" if self.turn == "white" else "white"

    def clone(self) -> "CheckersBoard":
        """Создает быструю поверхностную копию доски."""
        new_board = CheckersBoard.__new__(CheckersBoard)
        new_board.board = [row[:] for row in self.board]
        new_board.turn = self.turn
        new_board.active_jump_piece = self.active_jump_piece
        new_board.captured_in_turn = self.captured_in_turn[:]
        new_board.move_history = self.move_history[:]
        return new_board

