import pygame
import random
import copy
from settings import *
from pieces import Piece
from ai import DuckAI


class GameLogicMixin:
    """Handles Game Rules, Move Generation, and AI Integration"""

    def init_ai(self):
        # We stick to the standard array-based AI for now
        self.ai = DuckAI(depth=2)

    def init_board(self):
        setup = [(ROOK, 0, 0), (KNIGHT, 0, 1), (BISHOP, 0, 2), (QUEEN, 0, 3), (KING, 0, 4), (BISHOP, 0, 5),
                 (KNIGHT, 0, 6), (ROOK, 0, 7),
                 (ROOK, 7, 0), (KNIGHT, 7, 1), (BISHOP, 7, 2), (QUEEN, 7, 3), (KING, 7, 4), (BISHOP, 7, 5),
                 (KNIGHT, 7, 6), (ROOK, 7, 7)]
        for t, r, c in setup: self.board[r][c] = Piece('b' if r == 0 else 'w', t)
        for c in range(8): self.board[1][c], self.board[6][c] = Piece('b', PAWN), Piece('w', PAWN)

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

    def get_piece_legal_moves(self, r, c):
        p = self.board[r][c]
        if not p: return []
        moves = []

        def ok(nr, nc):
            return 0 <= nr < 8 and 0 <= nc < 8

        if p.type == KING:
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                if ok(nr, nc) and (nr, nc) != self.duck_pos:
                    t = self.board[nr][nc]
                    if not t or t.color != p.color: moves.append((nr, nc))
            if not p.has_moved:
                if self.can_castle(r, c, True): moves.append((r, 6))
                if self.can_castle(r, c, False): moves.append((r, 2))
            return moves

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

        if p.type == KNIGHT:
            for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
                nr, nc = r + dr, c + dc
                if ok(nr, nc) and (nr, nc) != self.duck_pos:
                    t = self.board[nr][nc]
                    if not t or t.color != p.color: moves.append((nr, nc))
            return moves

        if p.type == PAWN:
            d = -1 if p.color == 'w' else 1
            if ok(r + d, c) and not self.board[r + d][c] and (r + d, c) != self.duck_pos:
                moves.append((r + d, c))
                start_rank = 6 if p.color == 'w' else 1
                if r == start_rank and ok(r + d * 2, c) and not self.board[r + d * 2][c] and (
                r + d * 2, c) != self.duck_pos:
                    moves.append((r + d * 2, c))
            for dc in [-1, 1]:
                nr, nc = r + d, c + dc
                if ok(nr, nc):
                    t = self.board[nr][nc]
                    if t and t.color != p.color and (nr, nc) != self.duck_pos:
                        moves.append((nr, nc))
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
        if board_state is None: board_state = self.board
        king_pos = None
        for r in range(8):
            for c in range(8):
                p = board_state[r][c]
                if p and p.type == KING and p.color == color:
                    king_pos = (r, c)
                    break
            if king_pos: break
        if not king_pos: return False

        enemy = 'b' if color == 'w' else 'w'
        kr, kc = king_pos

        # Knights
        for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
            nr, nc = kr + dr, kc + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                p = board_state[nr][nc]
                if p and p.color == enemy and p.type == KNIGHT: return True

        # Sliding
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        for dr, dc in dirs:
            for i in range(1, 8):
                nr, nc = kr + dr * i, kc + dc * i
                if not (0 <= nr < 8 and 0 <= nc < 8): break
                if (nr, nc) == self.duck_pos: break
                p = board_state[nr][nc]
                if p:
                    if p.color == enemy:
                        if p.type == QUEEN: return True
                        if p.type == ROOK and (dr == 0 or dc == 0): return True
                        if p.type == BISHOP and (dr != 0 and dc != 0): return True
                    break

        # Pawns (Fixed Direction)
        pawn_dir = -1 if color == 'w' else 1
        for dc in [-1, 1]:
            nr, nc = kr + pawn_dir, kc + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                p = board_state[nr][nc]
                if p and p.color == enemy and p.type == PAWN: return True

        # Kings
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

    def execute_move(self, start, end, animated=True):
        sr, sc = start
        er, ec = end
        p = self.board[sr][sc]
        target = self.board[er][ec]
        sound = 'move'

        # 1. Sound Logic
        if target:
            sound = 'capture'
        elif p.type == PAWN and not target and sc != ec:
            sound = 'capture'

        # 2. Animation
        if animated and hasattr(self, 'animate_move_visual'):
            self.animate_move_visual(start, end, p, is_duck=False)

        # 3. Notation Generation
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

        # 4. Board Updates
        if p.type == PAWN and not target and sc != ec:
            self.board[sr][ec] = None

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

        # 5. King Capture / Game Over Handling
        if target and target.type == KING:
            self.game_over = True
            self.winner = self.turn
            sound = 'game_over'

            # --- FIX: LOG WINNING MOVE IMMEDIATELY ---
            final_move_str = move_str.replace("x", "") + "#"
            self.current_move_str = final_move_str

            if self.turn == 'w':
                self.move_log.append(f"{self.turn_number}. {final_move_str}")
            else:
                self.move_log.append(f"{self.turn_number}... {final_move_str}")

            self.save_snapshot()
            # -----------------------------------------

        if hasattr(self, 'play_sound'): self.play_sound(sound)

        # 6. Promotion / Next Phase
        if not self.game_over:
            promote_rank = 0 if p.color == 'w' else 7
            if p.type == PAWN and er == promote_rank:
                is_ai_turn = (self.game_mode == 'white_ai' and self.turn == 'w') or \
                             (self.game_mode == 'black_ai' and self.turn == 'b')

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

        self.phase = 'move_piece'
        self.turn = 'b' if self.turn == 'w' else 'w'
        self.save_snapshot()

        is_ai_next = (self.game_mode == 'white_ai' and self.turn == 'b') or \
                     (self.game_mode == 'black_ai' and self.turn == 'w')
        if is_ai_next:
            self.waiting_for_ai = True
            self.ai_wait_start = pygame.time.get_ticks()
        else:
            self.waiting_for_ai = False

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
                print("No moves available - Stalemate/Mate")
                self.game_over = True
                self.winner = 'b' if self.turn == 'w' else 'w'

        elif self.phase == 'move_duck':
            target = self.ai.get_duck_move(self.board, self.duck_pos, self.prev_duck_pos)
            if target: self.place_duck(target, animated=True)