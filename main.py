import pygame
import sys
import random
import os
import math
import copy

# --- Defaults ---
DEFAULT_WIDTH = 1050
DEFAULT_HEIGHT = 650
FPS = 60

# --- COLORS ---
WHITE_COLOR = (235, 236, 208)
BLACK_SQ_COLOR = (119, 149, 86)
HIGHLIGHT = (186, 202, 68)
LAST_MOVE_COLOR = (245, 235, 110, 160)
VALID_MOVE = (100, 200, 100, 150)
TEXT_COLOR = (20, 20, 20)
BG_COLOR = (40, 44, 52)
BOARD_BG_COLOR = (240, 240, 240)
PANEL_BG_COLOR = (50, 53, 60)
BUTTON_COLOR = (70, 130, 180)
BUTTON_HOVER = (100, 149, 237)
MENU_BG = (40, 44, 52)
ACTIVE_MOVE_BG = (80, 85, 95)
PROMOTION_BG = (255, 255, 255, 255)
EVAL_WHITE = (240, 240, 240)
EVAL_BLACK = (50, 50, 50)

# Unicode Fallback
UNICODE_PIECES = {
    'w': {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'},
    'b': {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟'}
}

KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN = 'K', 'Q', 'R', 'B', 'N', 'P'

# Piece values
PIECE_VALUES = {PAWN: 1, KNIGHT: 3, BISHOP: 3, ROOK: 5, QUEEN: 9, KING: 0}


class Piece:
    def __init__(self, color, type):
        self.color = color
        self.type = type
        self.has_moved = False


class DuckChess:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Duck Chess: Finals Edition")
        self.clock = pygame.time.Clock()

        self.game_mode = None
        self.player_side = 'w'
        self.state = 'menu'

        # Layout
        self.sq_size = 0
        self.board_x = 0
        self.board_y = 0
        self.ui_height = 60
        self.panel_width = 300
        self.eval_bar_width = 36
        self.side_margin = 20

        # Buttons
        self.nav_btns = {k: pygame.Rect(0, 0, 0, 0) for k in ['start', 'prev', 'next', 'end']}
        self.menu_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.flip_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.restart_btn_rect = pygame.Rect(0, 0, 0, 0)

        # Assets
        self.original_images = {}
        self.scaled_images = {}
        self.load_assets()

        # State Variables
        self.move_log = []
        self.current_move_str = ""
        self.turn_number = 1
        self.history = []
        self.view_index = -1

        # Draw Rules Counters
        self.half_move_clock = 0  # For 50-move rule
        self.repetition_history = {}  # Key: BoardHash, Value: Count

        # Promotion Specific
        self.promotion_pending = False
        self.promotion_coords = None
        self.promotion_options = []

        # Eval Animation
        self.target_eval_score = 0
        self.current_eval_score = 0.0

        self.resize_layout(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.reset_game_state()

    def load_assets(self):
        filename = "assets/pieces.png"
        if os.path.exists(filename):
            try:
                sheet = pygame.image.load(filename).convert_alpha()
                w, h = sheet.get_size()
                sw, sh = w // 6, h // 2
                piece_order = [QUEEN, KING, ROOK, KNIGHT, BISHOP, PAWN]
                row_map = {0: 'b', 1: 'w'}
                for row in range(2):
                    color = row_map[row]
                    for col in range(6):
                        rect = pygame.Rect(col * sw, row * sh, sw, sh)
                        self.original_images[f"{color}{piece_order[col]}"] = sheet.subsurface(rect)
            except:
                pass

        duck_file = "assets/duck.png"
        if os.path.exists(duck_file):
            try:
                self.original_images['duck'] = pygame.image.load(duck_file).convert_alpha()
            except:
                pass

    def resize_layout(self, w, h):
        self.screen_w = w
        self.screen_h = h
        available_w = w - self.panel_width - self.side_margin * 2
        available_h = h - self.ui_height - self.side_margin
        self.sq_size = min(available_w - self.eval_bar_width - self.side_margin, available_h) // 8
        board_width = self.sq_size * 8
        total_center_width = self.eval_bar_width + self.side_margin + board_width
        start_x = self.side_margin + (available_w - total_center_width) // 2
        self.eval_bar_x = start_x
        self.board_x = self.eval_bar_x + self.eval_bar_width + self.side_margin
        self.board_y = self.side_margin + (available_h - (self.sq_size * 8)) // 2

        self.font_large = pygame.font.SysFont("Segoe UI Symbol", int(self.sq_size * 0.8), bold=True)
        self.font_ui = pygame.font.SysFont("Arial", 16)
        self.font_history = pygame.font.SysFont("Consolas", 15)
        self.font_nav = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_menu = pygame.font.SysFont("Arial", 30, bold=True)
        self.font_eval = pygame.font.SysFont("Arial", 18, bold=True)

        self.scaled_images = {}
        for key, img in self.original_images.items():
            sz = int(self.sq_size * 0.8) if key == 'duck' else self.sq_size
            self.scaled_images[key] = pygame.transform.smoothscale(img, (sz, sz))

        px = w - self.panel_width
        bw, bh = self.panel_width // 4 - 10, 40
        by = h - 60
        self.nav_btns['start'] = pygame.Rect(px + 5, by, bw, bh)
        self.nav_btns['prev'] = pygame.Rect(px + 5 + bw + 10, by, bw, bh)
        self.nav_btns['next'] = pygame.Rect(px + 5 + (bw + 10) * 2, by, bw, bh)
        self.nav_btns['end'] = pygame.Rect(px + 5 + (bw + 10) * 3, by, bw, bh)

    def save_snapshot(self):
        self.history.append({
            'board': copy.deepcopy(self.board),
            'duck_pos': self.duck_pos,
            'prev_duck': self.prev_duck_pos,
            'last_move': self.last_move_arrow,
            'log': list(self.move_log)
        })
        self.view_index = len(self.history) - 1

    def reset_game_state(self):
        self.board = [[None] * 8 for _ in range(8)]
        self.init_board()
        self.duck_pos = (-1, -1)
        self.prev_duck_pos = (-1, -1)
        self.turn = 'w'
        self.phase = 'move_piece'
        self.selected_square = None
        self.valid_moves = []
        self.game_over = False
        self.winner = None
        self.en_passant_target = None
        self.waiting_for_ai = False
        self.move_log = []
        self.last_move_arrow = None
        self.turn_number = 1
        self.current_move_str = ""
        self.history = []
        self.promotion_pending = False
        self.target_eval_score = 0
        self.current_eval_score = 0.0

        # Reset counters
        self.half_move_clock = 0
        self.repetition_history = {}
        self.save_snapshot()

    def init_board(self):
        setup = [(ROOK, 0, 0), (KNIGHT, 0, 1), (BISHOP, 0, 2), (QUEEN, 0, 3), (KING, 0, 4), (BISHOP, 0, 5),
                 (KNIGHT, 0, 6), (ROOK, 0, 7),
                 (ROOK, 7, 0), (KNIGHT, 7, 1), (BISHOP, 7, 2), (QUEEN, 7, 3), (KING, 7, 4), (BISHOP, 7, 5),
                 (KNIGHT, 7, 6), (ROOK, 7, 7)]
        for t, r, c in setup: self.board[r][c] = Piece('b' if r == 0 else 'w', t)
        for c in range(8): self.board[1][c], self.board[6][c] = Piece('b', PAWN), Piece('w', PAWN)

    def get_notation_coords(self, r, c):
        return f"{'abcdefgh'[c]}{'87654321'[r]}"

    # --- Hash for Repetition ---
    def get_board_state_key(self):
        # Convert board to tuple of tuples
        board_tuple = tuple(tuple((p.color, p.type, p.has_moved) if p else None for p in row) for row in self.board)
        return (board_tuple, self.duck_pos, self.turn, self.en_passant_target)

    # --- Logic ---
    def calculate_material_score(self, board_state):
        score = 0
        for r in range(8):
            for c in range(8):
                p = board_state[r][c]
                if p:
                    val = PIECE_VALUES[p.type]
                    if p.color == 'w':
                        score += val
                    else:
                        score -= val
        return score

    def check_stalemate_or_draw(self):
        """Checks Stalemate, 50-Move Rule, and Repetition."""
        if self.game_over: return

        # 1. 50-Move Rule (100 half moves)
        if self.half_move_clock >= 100:
            self.game_over = True
            self.winner = "Draw (50-Move Rule)"
            return

        # 2. Threefold Repetition
        current_key = self.get_board_state_key()
        if self.repetition_history.get(current_key, 0) >= 3:
            self.game_over = True
            self.winner = "Draw (Repetition)"
            return

        # 3. Stalemate (No legal moves)
        # Scan ALL pieces for current turn. If 0 valid moves found, it's stalemate.
        any_legal_move = False
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p and p.color == self.turn:
                    moves = self.get_piece_legal_moves(r, c)
                    if moves:
                        any_legal_move = True
                        break
            if any_legal_move: break

        if not any_legal_move:
            self.game_over = True
            self.winner = "Draw (Stalemate)"

    def get_piece_legal_moves(self, r, c):
        p = self.board[r][c]
        if not p: return []
        moves = []

        def ok(nr, nc):
            return 0 <= nr < 8 and 0 <= nc < 8

        if p.type == KING and not p.has_moved:
            if self.can_castle(r, c, True): moves.append((r, 6))
            if self.can_castle(r, c, False): moves.append((r, 2))

        dirs = []
        if p.type in [KING, QUEEN]:
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif p.type == ROOK:
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        elif p.type == BISHOP:
            dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif p.type == KNIGHT:
            for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
                if ok(r + dr, c + dc) and (r + dr, c + dc) != self.duck_pos:
                    t = self.board[r + dr][c + dc]
                    if not t or t.color != p.color: moves.append((r + dr, c + dc))
            return moves
        elif p.type == PAWN:
            d = -1 if p.color == 'w' else 1
            if ok(r + d, c) and not self.board[r + d][c] and (r + d, c) != self.duck_pos:
                moves.append((r + d, c))
                s = 6 if p.color == 'w' else 1
                if r == s and ok(r + d * 2, c) and not self.board[r + d * 2][c] and (r + d * 2, c) != self.duck_pos:
                    moves.append((r + d * 2, c))
            for dc in [-1, 1]:
                if ok(r + d, c + dc):
                    t = self.board[r + d][c + dc]
                    if t and t.color != p.color and (r + d, c + dc) != self.duck_pos:
                        moves.append((r + d, c + dc))
                    elif not t and (r + d, c + dc) == self.en_passant_target and (r + d, c + dc) != self.duck_pos:
                        moves.append((r + d, c + dc))
            return moves

        dist = 1 if p.type == KING else 8
        for dr, dc in dirs:
            for i in range(1, dist + 1):
                nr, nc = r + dr * i, c + dc * i
                if not ok(nr, nc) or (nr, nc) == self.duck_pos: break
                t = self.board[nr][nc]
                if not t:
                    moves.append((nr, nc))
                else:
                    if t.color != p.color: moves.append((nr, nc))
                    break
        return moves

    def can_castle(self, r, c, is_ks):
        rc = 7 if is_ks else 0
        rook = self.board[r][rc]
        if not rook or rook.type != ROOK or rook.has_moved: return False
        cols = [5, 6] if is_ks else [1, 2, 3]
        for cl in cols:
            if self.board[r][cl] or (r, cl) == self.duck_pos: return False
        return True

    def execute_move(self, start, end):
        sr, sc = start
        er, ec = end
        p = self.board[sr][sc]
        target = self.board[er][ec]

        # 50-Move Rule Logic: Reset on Pawn move or Capture
        if p.type == PAWN or target is not None:
            self.half_move_clock = 0
        else:
            self.half_move_clock += 1

        pc = "" if p.type == PAWN else p.type
        cap = "x" if (target or (p.type == PAWN and sc != ec)) else ""
        ds = self.get_notation_coords(er, ec)
        if p.type == PAWN and cap == "x": pc = self.get_notation_coords(sr, sc)[0]
        self.current_move_str = f"{pc}{cap}{ds}"
        self.last_move_arrow = (start, end)

        if target and target.type == KING:
            self.game_over = True
            self.winner = self.turn

        if p.type == PAWN and not target and sc != ec: self.board[sr][ec] = None

        next_ep = None
        if p.type == PAWN and abs(sr - er) == 2: next_ep = ((sr + er) // 2, sc)

        if p.type == KING and abs(sc - ec) == 2:
            ks = (ec > sc)
            rc, nrc = (7, 5) if ks else (0, 3)
            self.board[sr][nrc], self.board[sr][rc] = self.board[sr][rc], None
            self.board[sr][nrc].has_moved = True

        self.board[er][ec], self.board[sr][sc] = p, None
        p.has_moved = True
        self.en_passant_target = next_ep

        if not self.game_over:
            promote_rank = 0 if p.color == 'w' else 7
            if p.type == PAWN and er == promote_rank:
                is_ai = (self.game_mode == 'white_ai' and self.turn == 'w') or \
                        (self.game_mode == 'black_ai' and self.turn == 'b')
                if is_ai:
                    p.type = QUEEN
                    self.current_move_str += "=Q"
                    self.prev_duck_pos = self.duck_pos
                    self.phase = 'move_duck'
                else:
                    self.promotion_pending = True
                    self.promotion_coords = (er, ec)
            else:
                self.prev_duck_pos = self.duck_pos
                self.phase = 'move_duck'

    def promote_pawn(self, type_char):
        r, c = self.promotion_coords
        self.board[r][c].type = type_char
        self.current_move_str += f"={type_char}"
        self.promotion_pending = False
        self.promotion_coords = None
        self.prev_duck_pos = self.duck_pos
        self.phase = 'move_duck'

    def place_duck(self, pos):
        if self.board[pos[0]][pos[1]] or pos == self.prev_duck_pos: return

        log_entry = f"{self.current_move_str} @ {self.get_notation_coords(pos[0], pos[1])}"
        if self.turn == 'w':
            self.move_log.append(f"{self.turn_number}. {log_entry}")
        else:
            self.move_log.append(f"{self.turn_number}... {log_entry}")
            self.turn_number += 1

        self.duck_pos = pos
        self.phase = 'move_piece'
        self.turn = 'b' if self.turn == 'w' else 'w'

        # --- Update Repetition History ---
        # Note: We do this AFTER the turn switch, but before the next player moves
        # But `self.turn` just switched. So the "state" is ready for the NEXT player.
        # We record the state at the start of the new turn.
        state_key = self.get_board_state_key()
        self.repetition_history[state_key] = self.repetition_history.get(state_key, 0) + 1

        self.save_snapshot()

        # --- Check Draw Conditions (Stalemate / 50-Move / Repetition) ---
        self.check_stalemate_or_draw()

        if not self.game_over:
            is_ai_next = (self.game_mode == 'white_ai' and self.turn == 'b') or \
                         (self.game_mode == 'black_ai' and self.turn == 'w')
            if is_ai_next:
                self.waiting_for_ai = True
                self.ai_wait_start = pygame.time.get_ticks()
            else:
                self.waiting_for_ai = False

    def get_promotion_rects(self):
        if not self.promotion_coords: return []
        r, c = self.promotion_coords
        bx, by = self.get_screen_pos(r, c)
        direction = 1 if self.turn == 'w' else -1
        menu_h = self.sq_size * 4
        menu_x = bx
        start_y = by + (self.sq_size * direction)
        if direction == -1: start_y = by - menu_h
        board_bottom = self.board_y + self.sq_size * 8
        if start_y < self.board_y:
            start_y = self.board_y
        elif start_y + menu_h > board_bottom:
            start_y = board_bottom - menu_h
        opts = [QUEEN, KNIGHT, ROOK, BISHOP]
        rects = []
        if direction == -1: opts.reverse()
        for i, p_type in enumerate(opts):
            rect = pygame.Rect(menu_x, start_y + i * self.sq_size, self.sq_size, self.sq_size)
            rects.append((rect, p_type))
        return rects

    def handle_click(self, pos):
        if self.promotion_pending:
            for rect, p_type in self.get_promotion_rects():
                if rect.collidepoint(pos):
                    self.promote_pawn(p_type)
                    return
            return

        if self.nav_btns['start'].collidepoint(pos): self.view_index = 0; return
        if self.nav_btns['prev'].collidepoint(pos): self.view_index = max(0, self.view_index - 1); return
        if self.nav_btns['next'].collidepoint(pos): self.view_index = min(len(self.history) - 1,
                                                                          self.view_index + 1); return
        if self.nav_btns['end'].collidepoint(pos): self.view_index = len(self.history) - 1; return

        if self.restart_btn_rect.collidepoint(pos): self.reset_game_state(); return
        if self.menu_btn_rect.collidepoint(pos): self.state = 'menu'; return
        if self.game_mode == 'pvp' and self.flip_btn_rect.collidepoint(pos):
            self.player_side = 'b' if self.player_side == 'w' else 'w';
            return

        is_live = (self.view_index == len(self.history) - 1)
        if not is_live or self.game_over or self.waiting_for_ai: return

        if not (self.board_x <= pos[0] < self.board_x + self.sq_size * 8 and
                self.board_y <= pos[1] < self.board_y + self.sq_size * 8): return

        r, c = self.get_board_pos(pos[0], pos[1])
        if r == -1: return

        if self.phase == 'move_piece':
            clk = self.board[r][c]
            if clk and clk.color == self.turn:
                self.selected_square = (r, c)
                self.valid_moves = self.get_piece_legal_moves(r, c)
            elif self.selected_square and (r, c) in self.valid_moves:
                self.execute_move(self.selected_square, (r, c))
                self.selected_square = None
                self.valid_moves = []
        elif self.phase == 'move_duck':
            self.place_duck((r, c))

    def handle_keyboard(self, event):
        if event.key == pygame.K_LEFT:
            self.view_index = max(0, self.view_index - 1)
        elif event.key == pygame.K_RIGHT:
            self.view_index = min(len(self.history) - 1, self.view_index + 1)

    def ai_turn(self):
        if self.view_index != len(self.history) - 1: return
        if self.game_over: return
        is_ai = (self.game_mode == 'white_ai' and self.turn == 'b') or \
                (self.game_mode == 'black_ai' and self.turn == 'w')
        if not is_ai: return

        if self.waiting_for_ai:
            if pygame.time.get_ticks() - self.ai_wait_start < 1000: return
            self.waiting_for_ai = False

        if self.phase == 'move_piece':
            moves = []
            for r in range(8):
                for c in range(8):
                    p = self.board[r][c]
                    if p and p.color == self.turn:
                        for m in self.get_piece_legal_moves(r, c): moves.append(((r, c), m))

            # AI Check Stalemate handled in place_duck, but double check empty moves here
            if not moves:
                # This should technically be caught by check_stalemate_or_draw earlier
                self.game_over = True
                self.winner = "Draw (Stalemate)"
                return

            pygame.time.wait(400)
            m = random.choice(moves)
            self.execute_move(m[0], m[1])
            return

        if self.phase == 'move_duck':
            pygame.time.wait(400)
            empties = [(r, c) for r in range(8) for c in range(8) if not self.board[r][c]]
            valid = [p for p in empties if p != self.prev_duck_pos]
            if valid:
                m = random.choice(valid)
                self.duck_pos = m
                self.draw_game()
                pygame.display.flip()
                pygame.time.wait(800)
                self.place_duck(m)
            elif empties:
                self.place_duck(random.choice(empties))

    def get_screen_pos(self, r, c):
        dr, dc = (7 - r, 7 - c) if self.player_side == 'b' else (r, c)
        return self.board_x + dc * self.sq_size, self.board_y + dr * self.sq_size

    def get_board_pos(self, px, py):
        rx, ry = px - self.board_x, py - self.board_y
        if rx < 0 or ry < 0: return -1, -1
        c, r = rx // self.sq_size, ry // self.sq_size
        if c >= 8 or r >= 8: return -1, -1
        return (7 - r, 7 - c) if self.player_side == 'b' else (r, c)

    def draw_promotion_ui(self):
        rects_and_types = self.get_promotion_rects()
        if not rects_and_types: return
        container = rects_and_types[0][0].unionall([r[0] for r in rects_and_types])
        pygame.draw.rect(self.screen, EVAL_WHITE, container, border_radius=0)
        pygame.draw.rect(self.screen, PANEL_BG_COLOR, container, width=2, border_radius=0)
        mouse_pos = pygame.mouse.get_pos()
        for rect, p_type in rects_and_types:
            if rect.collidepoint(mouse_pos): pygame.draw.rect(self.screen, HIGHLIGHT, rect)
            key = f"{self.turn}{p_type}"
            img = self.scaled_images.get(key)
            if img:
                self.screen.blit(img, rect)
            else:
                txt = self.font_large.render(UNICODE_PIECES[self.turn][p_type], True, TEXT_COLOR)
                self.screen.blit(txt, txt.get_rect(center=rect.center))

    def draw_eval_bar(self, current_board):
        if self.game_over:
            if self.winner == 'w':
                self.target_eval_score = 20
            elif self.winner == 'b':
                self.target_eval_score = -20
        else:
            self.target_eval_score = self.calculate_material_score(current_board)

        lerp_speed = 0.1
        diff = self.target_eval_score - self.current_eval_score
        if abs(diff) < 0.05:
            self.current_eval_score = self.target_eval_score
        else:
            self.current_eval_score += diff * lerp_speed

        score_to_draw = self.current_eval_score
        max_adv = 20
        clamped_score = max(-max_adv, min(max_adv, score_to_draw))
        normalized = (clamped_score + max_adv) / (2 * max_adv)

        bar_h = self.sq_size * 8
        bar_y = self.board_y
        bar_x = self.eval_bar_x
        bar_w = self.eval_bar_width

        mid_y = bar_y + bar_h * (1 - normalized)

        # Draw Top (Black)
        pygame.draw.rect(self.screen, EVAL_BLACK, (bar_x, bar_y, bar_w, mid_y - bar_y))

        # Draw Bottom (White)
        pygame.draw.rect(self.screen, EVAL_WHITE, (bar_x, mid_y, bar_w, bar_y + bar_h - mid_y))

        if self.game_over and self.winner in ['w', 'b']:
            col = EVAL_WHITE if self.winner == 'w' else EVAL_BLACK
            pygame.draw.rect(self.screen, col, (bar_x, bar_y, bar_w, bar_h))

        # --- Draw Text ---
        disp_score = int(round(self.current_eval_score))
        score_txt = f"{abs(disp_score)}"

        if normalized > 0.95:
            txt_col = TEXT_COLOR
        else:
            txt_col = EVAL_WHITE

        txt_surf = self.font_eval.render(score_txt, True, txt_col)
        # Fix text to TOP
        txt_rect = txt_surf.get_rect(center=(bar_x + bar_w // 2, bar_y + 15))
        self.screen.blit(txt_surf, txt_rect)

    def draw_history_panel(self):
        panel_rect = pygame.Rect(self.screen_w - self.panel_width, 0, self.panel_width, self.screen_h)
        pygame.draw.rect(self.screen, PANEL_BG_COLOR, panel_rect)
        title = self.font_ui.render("Game History", True, (255, 255, 255))
        self.screen.blit(title, (self.screen_w - self.panel_width + 10, 15))
        counter_str = f"{self.view_index} / {len(self.history) - 1}"
        counter_surf = self.font_ui.render(counter_str, True, (180, 180, 180))
        self.screen.blit(counter_surf, (self.screen_w - 70, 15))

        full_log = self.history[-1]['log']
        start_y = 50
        line_height = 25
        button_area_y = self.nav_btns['start'].top
        max_lines = (button_area_y - start_y) // line_height
        highlight_idx = self.view_index - 1
        scroll_offset = 0
        if highlight_idx > max_lines - 2: scroll_offset = highlight_idx - (max_lines - 2)
        moves = full_log[scroll_offset: scroll_offset + max_lines]

        for i, m_str in enumerate(moves):
            if (scroll_offset + i) == highlight_idx:
                h_rect = pygame.Rect(self.screen_w - self.panel_width, start_y + i * line_height, self.panel_width,
                                     line_height)
                pygame.draw.rect(self.screen, ACTIVE_MOVE_BG, h_rect)
            txt = self.font_history.render(m_str, True, (220, 220, 220))
            self.screen.blit(txt, (self.screen_w - self.panel_width + 10, start_y + i * line_height + 4))

        labels = [("<<", 'start'), ("<", 'prev'), (">", 'next'), (">>", 'end')]
        mouse = pygame.mouse.get_pos()
        for lbl, key in labels:
            r = self.nav_btns[key]
            c = BUTTON_HOVER if r.collidepoint(mouse) else BUTTON_COLOR
            pygame.draw.rect(self.screen, c, r, border_radius=5)
            t = self.font_nav.render(lbl, True, (255, 255, 255))
            self.screen.blit(t, t.get_rect(center=r.center))

    def draw_duck(self, r, c):
        x, y = self.get_screen_pos(r, c)
        if 'duck' in self.scaled_images:
            img = self.scaled_images['duck']
            offset = (self.sq_size - img.get_width()) // 2
            self.screen.blit(img, (x + offset, y + offset))
        else:
            cx, cy = x + self.sq_size // 2, y + self.sq_size // 2
            pygame.draw.circle(self.screen, (255, 220, 0), (cx, cy), self.sq_size // 3)

    def draw_game(self):
        self.screen.fill(BG_COLOR)
        self.draw_history_panel()
        is_live = (self.view_index == len(self.history) - 1)
        if is_live:
            board, d_pos, last_mv, prev_d = self.board, self.duck_pos, self.last_move_arrow, self.prev_duck_pos
        else:
            snap = self.history[self.view_index]
            board, d_pos, last_mv, prev_d = snap['board'], snap['duck_pos'], snap['last_move'], snap['prev_duck']

        self.draw_eval_bar(board)

        for r in range(8):
            for c in range(8):
                x, y = self.get_screen_pos(r, c)
                col = WHITE_COLOR if (r + c) % 2 == 0 else BLACK_SQ_COLOR
                pygame.draw.rect(self.screen, col, (x, y, self.sq_size, self.sq_size))
                if last_mv and ((r, c) == last_mv[0] or (r, c) == last_mv[1]):
                    s = pygame.Surface((self.sq_size, self.sq_size));
                    s.set_alpha(LAST_MOVE_COLOR[3]);
                    s.fill(LAST_MOVE_COLOR[:3]);
                    self.screen.blit(s, (x, y))
                if prev_d and (r, c) == prev_d:
                    s = pygame.Surface((self.sq_size, self.sq_size));
                    s.set_alpha(LAST_MOVE_COLOR[3]);
                    s.fill(LAST_MOVE_COLOR[:3]);
                    self.screen.blit(s, (x, y))
                if is_live and not self.promotion_pending:
                    if self.selected_square == (r, c): pygame.draw.rect(self.screen, HIGHLIGHT,
                                                                        (x, y, self.sq_size, self.sq_size))
                    if (r, c) in self.valid_moves: s = pygame.Surface((self.sq_size, self.sq_size)); s.set_alpha(
                        100); s.fill((0, 255, 0)); self.screen.blit(s, (x, y))
                if d_pos == (r, c): self.draw_duck(r, c)
                p = board[r][c]
                if p:
                    key = f"{p.color}{p.type}"
                    if key in self.scaled_images:
                        self.screen.blit(self.scaled_images[key], (x, y))
                    else:
                        txt = UNICODE_PIECES[p.color][p.type]
                        tc = (0, 0, 0) if p.color == 'b' else (255, 255, 255)
                        sf = self.font_large.render(txt, True, tc)
                        rc = sf.get_rect(center=(x + self.sq_size // 2, y + self.sq_size // 2))
                        if p.color == 'w': ol = self.font_large.render(txt, True, (0, 0, 0)); self.screen.blit(ol,
                                                                                                               ol.get_rect(
                                                                                                                   center=(
                                                                                                                   rc.centerx + 2,
                                                                                                                   rc.centery + 2)))
                        self.screen.blit(sf, rc)

        ui_y = self.screen_h - self.ui_height
        pygame.draw.rect(self.screen, BOARD_BG_COLOR, (0, ui_y, self.screen_w - self.panel_width, self.ui_height))
        status = f"WINNER: {self.winner}" if self.game_over else f"{'White' if self.turn == 'w' else 'Black'} | {'Move Piece' if self.phase == 'move_piece' else 'Place Duck'}"
        if not is_live:
            status = "VIEWING HISTORY"
        elif self.promotion_pending:
            status = "Select Promotion Piece!"
        txt = self.font_ui.render(status, True, TEXT_COLOR)
        self.screen.blit(txt, (15, ui_y + 20))

        mouse = pygame.mouse.get_pos()
        btns = [("Menu", self.menu_btn_rect), ("Restart", self.restart_btn_rect)]
        if self.game_mode == 'pvp': btns.insert(1, ("Flip", self.flip_btn_rect))
        start_x = self.screen_w - self.panel_width - (len(btns) * 110) - 10
        for i, (lbl, rect) in enumerate(btns):
            rect.width, rect.height = 100, 40
            rect.x, rect.centery = start_x + i * 110, ui_y + 30
            col = BUTTON_HOVER if rect.collidepoint(mouse) else BUTTON_COLOR
            pygame.draw.rect(self.screen, col, rect, border_radius=8)
            t = self.font_ui.render(lbl, True, (255, 255, 255))
            self.screen.blit(t, t.get_rect(center=rect.center))

        if self.promotion_pending and is_live:
            self.draw_promotion_ui()

    def draw_menu(self):
        self.screen.fill(MENU_BG)
        t = self.font_menu.render("DUCK CHESS", True, (255, 215, 0))
        self.screen.blit(t, t.get_rect(center=(self.screen_w // 2, self.screen_h * 0.2)))
        opts = [("Play as White", 'white_ai'), ("Play as Black", 'black_ai'), ("2 Player", 'pvp')]
        m = pygame.mouse.get_pos()
        for i, (txt, mode) in enumerate(opts):
            r = pygame.Rect(0, 0, 300, 60)
            r.center = (self.screen_w // 2, self.screen_h * 0.4 + i * 80)
            c = BUTTON_HOVER if r.collidepoint(m) else BUTTON_COLOR
            pygame.draw.rect(self.screen, c, r, border_radius=10)
            ts = self.font_ui.render(txt, True, (255, 255, 255))
            self.screen.blit(ts, ts.get_rect(center=r.center))
            if pygame.mouse.get_pressed()[0] and r.collidepoint(m):
                self.game_mode = mode
                self.player_side = 'b' if mode == 'black_ai' else 'w'
                self.reset_game_state()
                self.state = 'game'
                pygame.time.wait(200)

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                if event.type == pygame.VIDEORESIZE: self.resize_layout(event.w, event.h)
                if event.type == pygame.MOUSEBUTTONDOWN and self.state == 'game': self.handle_click(event.pos)
                if event.type == pygame.KEYDOWN and self.state == 'game': self.handle_keyboard(event)

            if self.state == 'menu':
                self.draw_menu()
            else:
                self.ai_turn()
                self.draw_game()
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    DuckChess().run()