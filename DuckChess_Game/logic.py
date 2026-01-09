import pygame
import random
import copy
from settings import *
from pieces import Piece
from ai import DuckAI


class GameLogicMixin:
    """Handles Game Rules, Move Generation, and AI Integration"""

    def init_ai(self):
        self.ai = DuckAI(depth=2)

    def init_board(self):
        setup = [(ROOK, 0, 0), (KNIGHT, 0, 1), (BISHOP, 0, 2), (QUEEN, 0, 3), (KING, 0, 4), (BISHOP, 0, 5),
                 (KNIGHT, 0, 6), (ROOK, 0, 7),
                 (ROOK, 7, 0), (KNIGHT, 7, 1), (BISHOP, 7, 2), (QUEEN, 7, 3), (KING, 7, 4), (BISHOP, 7, 5),
                 (KNIGHT, 7, 6), (ROOK, 7, 7)]
        for t, r, c in setup: self.board[r][c] = Piece('b' if r == 0 else 'w', t)
        for c in range(8): self.board[1][c], self.board[6][c] = Piece('b', PAWN), Piece('w', PAWN)

    # --- HELPERS ---
    def get_rank_file(self, r, c):
        return "87654321"[r], "abcdefgh"[c]

    def get_notation_coords(self, r, c):
        return f"{'abcdefgh'[c]}{'87654321'[r]}"

    def calculate_material_score(self, board_state):
        score = 0
        for r in range(8):
            for c in range(8):
                p = board_state[r][c]
                if p: score += PIECE_VALUES[p.type] * (1 if p.color == 'w' else -1)
        return score

    # --- STATE HASHING (For 3-Fold Repetition) ---
    def generate_fen_signature(self):
        """Generates a unique string representing the current board state + duck + turn."""
        board_str = ""
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p:
                    board_str += f"{p.color}{p.type}"
                else:
                    board_str += "."

        # We must include the Duck, En Passant, and Turn in the hash
        return f"{board_str}|{self.duck_pos}|{self.turn}|{self.en_passant_target}"

    # --- MOVE GENERATION ---
    def get_piece_legal_moves(self, r, c):
        p = self.board[r][c]
        if not p: return []
        moves = []

        def ok(nr, nc):
            return 0 <= nr < 8 and 0 <= nc < 8

        # 1. King Moves
        if p.type == KING:
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                if ok(nr, nc) and (nr, nc) != self.duck_pos:
                    t = self.board[nr][nc]
                    if not t or t.color != p.color: moves.append((nr, nc))
            # Castling
            if not p.has_moved:
                if self.can_castle(r, c, True): moves.append((r, 6))
                if self.can_castle(r, c, False): moves.append((r, 2))
            return moves

        # 2. Sliding Pieces (Queen, Rook, Bishop)
        dirs = []
        if p.type == QUEEN:
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif p.type == ROOK:
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        elif p.type == BISHOP:
            dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

        if dirs:
            for dr, dc in dirs:
                for i in range(1, 8):
                    nr, nc = r + dr * i, c + dc * i
                    if not ok(nr, nc) or (nr, nc) == self.duck_pos: break
                    t = self.board[nr][nc]
                    if not t:
                        moves.append((nr, nc))
                    else:
                        if t.color != p.color: moves.append((nr, nc))
                        break
            return moves

        # 3. Knight Moves
        if p.type == KNIGHT:
            for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
                nr, nc = r + dr, c + dc
                if ok(nr, nc) and (nr, nc) != self.duck_pos:
                    t = self.board[nr][nc]
                    if not t or t.color != p.color: moves.append((nr, nc))
            return moves

        # 4. Pawn Moves
        if p.type == PAWN:
            d = -1 if p.color == 'w' else 1
            # Forward 1
            if ok(r + d, c) and not self.board[r + d][c] and (r + d, c) != self.duck_pos:
                moves.append((r + d, c))
                # Forward 2
                start_rank = 6 if p.color == 'w' else 1
                if r == start_rank and ok(r + d * 2, c) and not self.board[r + d * 2][c] and (
                r + d * 2, c) != self.duck_pos:
                    moves.append((r + d * 2, c))
            # Captures
            for dc in [-1, 1]:
                nr, nc = r + d, c + dc
                if ok(nr, nc):
                    t = self.board[nr][nc]
                    # Normal Capture
                    if t and t.color != p.color and (nr, nc) != self.duck_pos:
                        moves.append((nr, nc))
                    # En Passant
                    elif not t and (nr, nc) == self.en_passant_target and (nr, nc) != self.duck_pos:
                        moves.append((nr, nc))
            return moves
        return []

    def can_castle(self, r, c, is_ks):
        rc = 7 if is_ks else 0
        rook = self.board[r][rc]
        if not rook or rook.type != ROOK or rook.has_moved: return False
        path_cols = [5, 6] if is_ks else [1, 2, 3]
        for cl in path_cols:
            if self.board[r][cl] or (r, cl) == self.duck_pos: return False
        return True

    def is_in_check(self, color, board_state=None):
        """Checks if the King is under attack. Note: In Duck Chess, check is valid but not game-ending."""
        if board_state is None: board_state = self.board
        king_pos = None
        for r in range(8):
            for c in range(8):
                p = board_state[r][c]
                if p and p.type == KING and p.color == color:
                    king_pos = (r, c)
                    break
            if king_pos: break
        if not king_pos: return False  # King captured?

        enemy = 'b' if color == 'w' else 'w'
        kr, kc = king_pos

        # Check Knights
        for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
            nr, nc = kr + dr, kc + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                p = board_state[nr][nc]
                if p and p.color == enemy and p.type == KNIGHT: return True

        # Check Sliding
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        for dr, dc in dirs:
            for i in range(1, 8):
                nr, nc = kr + dr * i, kc + dc * i
                if not (0 <= nr < 8 and 0 <= nc < 8): break
                if (nr, nc) == self.duck_pos: break  # Duck blocks checks!
                p = board_state[nr][nc]
                if p:
                    if p.color == enemy:
                        if p.type == QUEEN: return True
                        if p.type == ROOK and (dr == 0 or dc == 0): return True
                        if p.type == BISHOP and (dr != 0 and dc != 0): return True
                    break

        # Check Pawns
        pawn_dir = -1 if color == 'w' else 1
        for dc in [-1, 1]:
            nr, nc = kr + pawn_dir, kc + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                p = board_state[nr][nc]
                if p and p.color == enemy and p.type == PAWN: return True

        # Check Enemy King
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                nr, nc = kr + dr, kc + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    p = board_state[nr][nc]
                    if p and p.color == enemy and p.type == KING: return True
        return False

    def get_disambiguation(self, start, end, piece):
        if piece.type == PAWN: return ""
        duplicates = []
        sr, sc = start
        for r in range(8):
            for c in range(8):
                if (r, c) == start: continue
                p = self.board[r][c]
                if p and p.type == piece.type and p.color == piece.color:
                    moves = self.get_piece_legal_moves(r, c)
                    if end in moves: duplicates.append((r, c))
        if not duplicates: return ""
        files_differ = True
        ranks_differ = True
        for (dr, dc) in duplicates:
            if dc == sc: files_differ = False
            if dr == sr: ranks_differ = False
        start_rank, start_file = self.get_rank_file(sr, sc)
        if files_differ: return start_file
        if ranks_differ: return start_rank
        return start_file + start_rank

    # --- MAIN MOVE EXECUTION ---
    def execute_move(self, start, end, animated=True):
        sr, sc = start
        er, ec = end
        p = self.board[sr][sc]
        target = self.board[er][ec]
        sound = 'move'

        # --- 50-Move Rule Logic: Reset on Pawn move or Capture ---
        if p.type == PAWN or target is not None:
            self.half_move_clock = 0
        else:
            self.half_move_clock += 1

        # Sound Logic
        if target:
            sound = 'capture'
        elif p.type == PAWN and not target and sc != ec:
            sound = 'capture'

        # Animation
        if animated and hasattr(self, 'animate_move_visual'):
            self.animate_move_visual(start, end, p, is_duck=False)

        # Notation
        move_str = ""
        if p.type == KING and abs(sc - ec) == 2:
            move_str = "O-O" if ec > sc else "O-O-O"
            sound = 'castle'
        else:
            if p.type != PAWN:
                move_str += p.type
                move_str += self.get_disambiguation(start, end, p)
            is_capture = (target is not None) or (p.type == PAWN and sc != ec and not target)
            if is_capture:
                if p.type == PAWN: move_str += self.get_notation_coords(sr, sc)[0]
                move_str += "x"
                sound = 'capture'
            move_str += self.get_notation_coords(er, ec)

        # Update Board
        if p.type == PAWN and not target and sc != ec:
            self.board[sr][ec] = None  # En Passant Capture

        if p.type == KING and abs(sc - ec) == 2:
            ks = (ec > sc)
            rc, nrc = (7, 5) if ks else (0, 3)
            self.board[sr][nrc], self.board[sr][rc] = self.board[sr][rc], None
            self.board[sr][nrc].has_moved = True

        self.board[er][ec], self.board[sr][sc] = p, None
        p.has_moved = True

        next_ep = None
        if p.type == PAWN and abs(sr - er) == 2: next_ep = ((sr + er) // 2, sc)
        self.en_passant_target = next_ep

        enemy_color = 'b' if self.turn == 'w' else 'w'
        if self.is_in_check(enemy_color): move_str += "+"

        self.current_move_str = move_str
        self.last_move_arrow = (start, end)

        # King Capture Check
        if target and target.type == KING:
            self.game_over = True
            self.winner = self.turn
            sound = 'game_over'
            final_move_str = move_str.replace("x", "") + "#"
            self.current_move_str = final_move_str
            if self.turn == 'w':
                self.move_log.append(f"{self.turn_number}. {final_move_str}")
            else:
                self.move_log.append(f"{self.turn_number}... {final_move_str}")
            self.save_snapshot()

        if hasattr(self, 'play_sound'): self.play_sound(sound)

        # Promotion / Next Phase
        if not self.game_over:
            promote_rank = 0 if p.color == 'w' else 7
            if p.type == PAWN and er == promote_rank:

                # --- BUG FIX: Check if it is actually the AI's turn ---
                # If mode is 'white_ai' (User=White), AI plays Black ('b')
                # If mode is 'black_ai' (User=Black), AI plays White ('w')
                is_ai_turn = (self.game_mode == 'white_ai' and self.turn == 'b') or \
                             (self.game_mode == 'black_ai' and self.turn == 'w')
                # -----------------------------------------------------

                if is_ai_turn:
                    p.type = random.choice([QUEEN, ROOK, BISHOP, KNIGHT])
                    self.current_move_str += f"={p.type}"
                    if hasattr(self, 'play_sound'): self.play_sound('promote')
                    self.prev_duck_pos = self.duck_pos
                    self.phase = 'move_duck'
                else:
                    self.promotion_pending = True
                    self.promotion_coords = (er, ec)
                    if hasattr(self, 'play_sound'): self.play_sound('notify')
            else:
                self.prev_duck_pos = self.duck_pos
                self.phase = 'move_duck'

    def promote_pawn(self, type_char):
        r, c = self.promotion_coords
        self.board[r][c].type = type_char
        self.current_move_str += f"={type_char}"
        enemy_color = 'b' if self.turn == 'w' else 'w'
        if self.is_in_check(enemy_color):
            if "+" not in self.current_move_str: self.current_move_str += "+"
        self.promotion_pending = False
        self.promotion_coords = None
        if hasattr(self, 'play_sound'): self.play_sound('promote')
        self.prev_duck_pos = self.duck_pos
        self.phase = 'move_duck'

    def place_duck(self, pos, animated=True):
        if self.board[pos[0]][pos[1]] or pos == self.prev_duck_pos: return

        if animated and self.duck_pos != (-1, -1) and hasattr(self, 'animate_move_visual'):
            self.animate_move_visual(self.duck_pos, pos, None, is_duck=True)

        log_entry = f"{self.current_move_str} @ {self.get_notation_coords(pos[0], pos[1])}"
        if self.turn == 'w':
            self.move_log.append(f"{self.turn_number}. {log_entry}")
        else:
            self.move_log.append(f"{self.turn_number}... {log_entry}")
            self.turn_number += 1

        self.duck_pos = pos
        if hasattr(self, 'play_sound'): self.play_sound('notify')

        # --- UPDATE STATE ---
        self.phase = 'move_piece'
        self.turn = 'b' if self.turn == 'w' else 'w'
        self.save_snapshot()

        # --- CHECK 3-FOLD, 50-MOVE, AND STALEMATE ---
        self.check_game_end_conditions()

        # AI Turn Trigger
        is_ai_next = (self.game_mode == 'white_ai' and self.turn == 'b') or \
                     (self.game_mode == 'black_ai' and self.turn == 'w')
        if is_ai_next and not self.game_over:
            self.waiting_for_ai = True
            self.ai_wait_start = pygame.time.get_ticks()
        else:
            self.waiting_for_ai = False

    def check_game_end_conditions(self):
        """Checks for 50-move rule, 3-fold repetition, and Stalemate (Loss)."""
        if self.game_over: return

        # 1. 50-Move Rule (100 half-moves)
        if self.half_move_clock >= 100:
            self.game_over = True
            self.winner = 'draw'
            print("Game Over: 50-Move Rule")
            return

        # 2. 3-Fold Repetition
        # Create a unique hash for the current situation (Board + Duck + Turn)
        signature = self.generate_fen_signature()
        self.rep_history[signature] = self.rep_history.get(signature, 0) + 1
        if self.rep_history[signature] >= 3:
            self.game_over = True
            self.winner = 'draw'
            print("Game Over: 3-Fold Repetition")
            return

        # 3. Stalemate Logic (Player has no legal moves -> LOSS)
        has_moves = False
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p and p.color == self.turn:
                    if self.get_piece_legal_moves(r, c):
                        has_moves = True
                        break
            if has_moves: break

        if not has_moves:
            self.game_over = True
            # Winner is the person who JUST moved (the previous turn)
            self.winner = 'b' if self.turn == 'w' else 'w'
            print(f"Game Over: Stalemate (Win for {self.winner.upper()})")

    def ai_turn(self):
        if self.view_index != len(self.history) - 1: return
        if self.game_over: return
        if not self.waiting_for_ai: return
        if pygame.time.get_ticks() - self.ai_wait_start < 400: return

        if self.phase == 'move_piece':
            move = self.ai.get_piece_move(self.board, self.turn, self.get_piece_legal_moves)
            if move:
                self.execute_move(move[0], move[1], animated=True)
            else:
                # This should technically be caught by check_game_end_conditions,
                # but we keep it as a fallback.
                self.game_over = True
                self.winner = 'b' if self.turn == 'w' else 'w'

        elif self.phase == 'move_duck':
            target = self.ai.get_duck_move(self.board, self.duck_pos, self.prev_duck_pos)
            if target: self.place_duck(target, animated=True)

    def clear_board(self):
        """Removes all pieces from the board."""
        self.board = [[None] * 8 for _ in range(8)]
        self.duck_pos = (-1, -1)
        self.turn = 'w'
        self.move_log = []
        self.history = []

    def set_piece(self, r, c, piece_type, color):
        """Manually places a piece."""
        if piece_type == 'duck':
            self.duck_pos = (r, c)
            self.board[r][c] = None  # Duck cannot share square
        else:
            if self.duck_pos == (r, c): self.duck_pos = (-1, -1)
            self.board[r][c] = Piece(color, piece_type)

    def validate_editor_board(self):
        """Ensures the custom board is playable (Kings exist)."""
        w_king = sum(1 for r in range(8) for c in range(8) if
                     self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'w')
        b_king = sum(1 for r in range(8) for c in range(8) if
                     self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'b')
        return w_king == 1 and b_king == 1