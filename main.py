import pygame
import sys
import random
import os
import math
import copy

# --- Defaults ---
DEFAULT_WIDTH = 950
DEFAULT_HEIGHT = 650
FPS = 60

# --- COLORS ---
WHITE_COLOR = (235, 236, 208)
BLACK_SQ_COLOR = (119, 149, 86)
HIGHLIGHT = (186, 202, 68)  # Selection Green
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

# Unicode Fallback
UNICODE_PIECES = {
    'w': {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'},
    'b': {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟'}
}

KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN = 'K', 'Q', 'R', 'B', 'N', 'P'


class Piece:
    def __init__(self, color, type):
        self.color = color
        self.type = type
        self.has_moved = False


class DuckChess:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Duck Chess: Highlights Edition")
        self.clock = pygame.time.Clock()

        # Game State
        self.game_mode = None
        self.player_side = 'w'
        self.state = 'menu'

        # Layout Variables
        self.sq_size = 0
        self.board_x = 0
        self.board_y = 0
        self.ui_height = 60
        self.panel_width = 300

        # Nav Buttons
        self.nav_btns = {
            'start': pygame.Rect(0, 0, 0, 0),
            'prev': pygame.Rect(0, 0, 0, 0),
            'next': pygame.Rect(0, 0, 0, 0),
            'end': pygame.Rect(0, 0, 0, 0)
        }

        # Menu Buttons
        self.menu_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.flip_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.restart_btn_rect = pygame.Rect(0, 0, 0, 0)

        # Assets
        self.original_images = {}
        self.scaled_images = {}
        self.load_assets()

        # History
        self.move_log = []
        self.current_move_str = ""
        self.turn_number = 1

        # Snapshot History
        self.history = []
        self.view_index = -1

        self.resize_layout(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.reset_game_state()

    def load_assets(self):
        filename = "assets/pieces.png"
        if os.path.exists(filename):
            try:
                sheet = pygame.image.load(filename).convert_alpha()
                w, h = sheet.get_size()
                cols, rows = 6, 2
                sw, sh = w // cols, h // rows
                piece_order = [QUEEN, KING, ROOK, KNIGHT, BISHOP, PAWN]
                row_map = {0: 'b', 1: 'w'}
                for row in range(rows):
                    color = row_map[row]
                    for col in range(cols):
                        rect = pygame.Rect(col * sw, row * sh, sw, sh)
                        self.original_images[f"{color}{piece_order[col]}"] = sheet.subsurface(rect)
            except Exception as e:
                print(f"Error loading pieces: {e}")

        duck_file = "assets/duck.png"
        if os.path.exists(duck_file):
            try:
                self.original_images['duck'] = pygame.image.load(duck_file).convert_alpha()
            except:
                pass

    def resize_layout(self, w, h):
        self.screen_w = w
        self.screen_h = h

        available_w = w - self.panel_width
        available_h = h - self.ui_height
        board_dim = min(available_w, available_h)
        self.sq_size = board_dim // 8

        self.board_x = (available_w - (self.sq_size * 8)) // 2
        self.board_y = (available_h - (self.sq_size * 8)) // 2

        # Fonts
        self.font_large = pygame.font.SysFont("Segoe UI Symbol", int(self.sq_size * 0.8), bold=True)
        self.font_ui = pygame.font.SysFont("Arial", 16)
        self.font_history = pygame.font.SysFont("Consolas", 15)
        self.font_nav = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_menu = pygame.font.SysFont("Arial", 30, bold=True)

        # Scale Images
        self.scaled_images = {}
        for key, img in self.original_images.items():
            if key == 'duck':
                sz = int(self.sq_size * 0.8)
                self.scaled_images[key] = pygame.transform.smoothscale(img, (sz, sz))
            else:
                self.scaled_images[key] = pygame.transform.smoothscale(img, (self.sq_size, self.sq_size))

        # Position Navigation Buttons
        panel_x = w - self.panel_width
        btn_w = self.panel_width // 4 - 10
        btn_h = 40
        btn_y = h - 60

        self.nav_btns['start'] = pygame.Rect(panel_x + 5, btn_y, btn_w, btn_h)
        self.nav_btns['prev'] = pygame.Rect(panel_x + 5 + btn_w + 10, btn_y, btn_w, btn_h)
        self.nav_btns['next'] = pygame.Rect(panel_x + 5 + (btn_w + 10) * 2, btn_y, btn_w, btn_h)
        self.nav_btns['end'] = pygame.Rect(panel_x + 5 + (btn_w + 10) * 3, btn_y, btn_w, btn_h)

    def save_snapshot(self):
        # We need to save prev_duck_pos in snapshot to visualize history correctly later if desired
        snapshot = {
            'board': copy.deepcopy(self.board),
            'duck_pos': self.duck_pos,
            'prev_duck': self.prev_duck_pos,
            'last_move': self.last_move_arrow,  # reusing this variable name for piece move coords
            'log': list(self.move_log)
        }
        self.history.append(snapshot)
        self.view_index = len(self.history) - 1

    def reset_game_state(self):
        self.board = [[None for _ in range(8)] for _ in range(8)]
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
        self.last_move_arrow = None  # Stores ((start_r, c), (end_r, c))
        self.turn_number = 1
        self.current_move_str = ""

        self.history = []
        self.save_snapshot()

    def init_board(self):
        setup = [
            (ROOK, 0, 0), (KNIGHT, 0, 1), (BISHOP, 0, 2), (QUEEN, 0, 3), (KING, 0, 4), (BISHOP, 0, 5), (KNIGHT, 0, 6),
            (ROOK, 0, 7),
            (ROOK, 7, 0), (KNIGHT, 7, 1), (BISHOP, 7, 2), (QUEEN, 7, 3), (KING, 7, 4), (BISHOP, 7, 5), (KNIGHT, 7, 6),
            (ROOK, 7, 7)
        ]
        for p_type, r, c in setup:
            self.board[r][c] = Piece('b' if r == 0 else 'w', p_type)
        for c in range(8):
            self.board[1][c] = Piece('b', PAWN)
            self.board[6][c] = Piece('w', PAWN)

    def get_notation_coords(self, r, c):
        cols = 'abcdefgh'
        rows = '87654321'
        return f"{cols[c]}{rows[r]}"

    # --- Logic ---
    def get_piece_legal_moves(self, r, c):
        piece = self.board[r][c]
        if not piece: return []
        moves = []

        def is_valid(nr, nc):
            return 0 <= nr < 8 and 0 <= nc < 8

        if piece.type == KING and not piece.has_moved:
            if self.can_castle(r, c, True): moves.append((r, 6))
            if self.can_castle(r, c, False): moves.append((r, 2))

        directions = []
        if piece.type in [KING, QUEEN]:
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece.type == ROOK:
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        elif piece.type == BISHOP:
            directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece.type == KNIGHT:
            for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
                nr, nc = r + dr, c + dc
                if is_valid(nr, nc) and (nr, nc) != self.duck_pos:
                    target = self.board[nr][nc]
                    if target is None or target.color != piece.color: moves.append((nr, nc))
            return moves
        elif piece.type == PAWN:
            d = -1 if piece.color == 'w' else 1
            if is_valid(r + d, c) and not self.board[r + d][c] and (r + d, c) != self.duck_pos:
                moves.append((r + d, c))
                start = 6 if piece.color == 'w' else 1
                if r == start and is_valid(r + d * 2, c) and not self.board[r + d * 2][c] and (
                r + d * 2, c) != self.duck_pos:
                    moves.append((r + d * 2, c))
            for dc in [-1, 1]:
                if is_valid(r + d, c + dc):
                    target = self.board[r + d][c + dc]
                    if target and target.color != piece.color and (r + d, c + dc) != self.duck_pos:
                        moves.append((r + d, c + dc))
                    elif target is None and (r + d, c + dc) == self.en_passant_target and (
                    r + d, c + dc) != self.duck_pos:
                        moves.append((r + d, c + dc))
            return moves

        max_dist = 1 if piece.type == KING else 8
        for dr, dc in directions:
            for dist in range(1, max_dist + 1):
                nr, nc = r + dr * dist, c + dc * dist
                if not is_valid(nr, nc) or (nr, nc) == self.duck_pos: break
                target = self.board[nr][nc]
                if target is None:
                    moves.append((nr, nc))
                else:
                    if target.color != piece.color: moves.append((nr, nc))
                    break
        return moves

    def can_castle(self, r, c, is_kingside):
        rook_col = 7 if is_kingside else 0
        rook = self.board[r][rook_col]
        if not rook or rook.type != ROOK or rook.has_moved: return False
        path_cols = [5, 6] if is_kingside else [1, 2, 3]
        for col in path_cols:
            if self.board[r][col] is not None or (r, col) == self.duck_pos: return False
        return True

    def execute_move(self, start, end):
        sr, sc = start
        er, ec = end
        piece = self.board[sr][sc]
        target = self.board[er][ec]

        # Notation
        piece_char = "" if piece.type == PAWN else piece.type
        capture_char = "x" if (target or (piece.type == PAWN and sc != ec)) else ""
        dest_str = self.get_notation_coords(er, ec)
        if piece.type == PAWN and capture_char == "x": piece_char = self.get_notation_coords(sr, sc)[0]
        self.current_move_str = f"{piece_char}{capture_char}{dest_str}"
        self.last_move_arrow = (start, end)

        # Logic
        if target and target.type == KING:
            self.game_over = True
            self.winner = self.turn

        if piece.type == PAWN and target is None and sc != ec:
            self.board[sr][ec] = None

        next_ep = None
        if piece.type == PAWN and abs(sr - er) == 2:
            next_ep = ((sr + er) // 2, sc)

        if piece.type == KING and abs(sc - ec) == 2:
            is_kingside = (ec > sc)
            rook_col, new_rook_col = (7, 5) if is_kingside else (0, 3)
            rook = self.board[sr][rook_col]
            self.board[sr][new_rook_col] = rook
            self.board[sr][rook_col] = None
            rook.has_moved = True

        self.board[er][ec] = piece
        self.board[sr][sc] = None
        piece.has_moved = True
        self.en_passant_target = next_ep

        if not self.game_over:
            self.prev_duck_pos = self.duck_pos
            self.phase = 'move_duck'

    def place_duck(self, pos):
        if self.board[pos[0]][pos[1]] is not None or pos == self.prev_duck_pos: return

        duck_str = self.get_notation_coords(pos[0], pos[1])
        full_log_entry = f"{self.current_move_str} @ {duck_str}"

        if self.turn == 'w':
            self.move_log.append(f"{self.turn_number}. {full_log_entry}")
        else:
            self.move_log.append(f"{self.turn_number}... {full_log_entry}")
            self.turn_number += 1

        self.duck_pos = pos
        self.phase = 'move_piece'
        self.turn = 'b' if self.turn == 'w' else 'w'

        self.save_snapshot()

        next_turn_is_ai = (self.game_mode == 'white_ai' and self.turn == 'b') or \
                          (self.game_mode == 'black_ai' and self.turn == 'w')
        if next_turn_is_ai:
            self.waiting_for_ai = True
            self.ai_wait_start = pygame.time.get_ticks()
        else:
            self.waiting_for_ai = False

    def handle_click(self, pos):
        # Nav buttons
        if self.nav_btns['start'].collidepoint(pos): self.view_index = 0; return
        if self.nav_btns['prev'].collidepoint(pos): self.view_index = max(0, self.view_index - 1); return
        if self.nav_btns['next'].collidepoint(pos): self.view_index = min(len(self.history) - 1,
                                                                          self.view_index + 1); return
        if self.nav_btns['end'].collidepoint(pos): self.view_index = len(self.history) - 1; return

        # UI Buttons
        if self.restart_btn_rect.collidepoint(pos): self.reset_game_state(); return
        if self.menu_btn_rect.collidepoint(pos): self.state = 'menu'; return
        if self.game_mode == 'pvp' and self.flip_btn_rect.collidepoint(pos):
            self.player_side = 'b' if self.player_side == 'w' else 'w';
            return

        # Block moves if viewing history
        is_live = (self.view_index == len(self.history) - 1)
        if not is_live: return

        if self.game_over or self.waiting_for_ai: return

        if pos[0] > self.screen_w - self.panel_width: return

        r, c = self.get_board_pos(pos[0], pos[1])
        if r == -1: return

        if self.phase == 'move_piece':
            clicked = self.board[r][c]
            if clicked and clicked.color == self.turn:
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
        is_live = (self.view_index == len(self.history) - 1)
        if not is_live: return

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
            if not moves: self.turn = 'w' if self.turn == 'b' else 'b'; return

            pygame.time.wait(400)
            move = random.choice(moves)
            self.execute_move(move[0], move[1])
            return

        if self.phase == 'move_duck':
            pygame.time.wait(400)
            empties = [(r, c) for r in range(8) for c in range(8) if self.board[r][c] is None]
            valid = [p for p in empties if p != self.prev_duck_pos]
            if valid:
                move = random.choice(valid)
                self.duck_pos = move
                self.draw_game()
                pygame.display.flip()
                pygame.time.wait(800)
                self.place_duck(move)
            elif empties:
                self.place_duck(random.choice(empties))

    # --- Drawing ---
    def get_screen_pos(self, r, c):
        dr, dc = (7 - r, 7 - c) if self.player_side == 'b' else (r, c)
        return self.board_x + dc * self.sq_size, self.board_y + dr * self.sq_size

    def get_board_pos(self, px, py):
        rx, ry = px - self.board_x, py - self.board_y
        if rx < 0 or ry < 0: return -1, -1
        c, r = rx // self.sq_size, ry // self.sq_size
        if c >= 8 or r >= 8: return -1, -1
        return (7 - r, 7 - c) if self.player_side == 'b' else (r, c)

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
        if highlight_idx > max_lines - 2:
            scroll_offset = highlight_idx - (max_lines - 2)

        moves_to_draw = full_log[scroll_offset: scroll_offset + max_lines]

        for i, move_str in enumerate(moves_to_draw):
            actual_idx = scroll_offset + i
            if actual_idx == highlight_idx:
                highlight_rect = pygame.Rect(self.screen_w - self.panel_width, start_y + i * line_height,
                                             self.panel_width, line_height)
                pygame.draw.rect(self.screen, ACTIVE_MOVE_BG, highlight_rect)
            txt = self.font_history.render(move_str, True, (220, 220, 220))
            self.screen.blit(txt, (self.screen_w - self.panel_width + 10, start_y + i * line_height + 4))

        labels = [("<<", 'start'), ("<", 'prev'), (">", 'next'), (">>", 'end')]
        mouse = pygame.mouse.get_pos()
        for lbl, key in labels:
            rect = self.nav_btns[key]
            col = BUTTON_HOVER if rect.collidepoint(mouse) else BUTTON_COLOR
            pygame.draw.rect(self.screen, col, rect, border_radius=5)
            t = self.font_nav.render(lbl, True, (255, 255, 255))
            self.screen.blit(t, t.get_rect(center=rect.center))

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
            draw_board = self.board
            draw_duck_pos = self.duck_pos
            last_move_info = self.last_move_arrow
            prev_duck_info = self.prev_duck_pos
        else:
            snapshot = self.history[self.view_index]
            draw_board = snapshot['board']
            draw_duck_pos = snapshot['duck_pos']
            last_move_info = snapshot.get('last_move')
            prev_duck_info = snapshot.get('prev_duck')

        # Draw Board
        for r in range(8):
            for c in range(8):
                x, y = self.get_screen_pos(r, c)
                color = WHITE_COLOR if (r + c) % 2 == 0 else BLACK_SQ_COLOR
                pygame.draw.rect(self.screen, color, (x, y, self.sq_size, self.sq_size))

                # 1. HIGHLIGHT LAST MOVE (Start & End squares of piece)
                if last_move_info:
                    start_move, end_move = last_move_info
                    if (r, c) == start_move or (r, c) == end_move:
                        s = pygame.Surface((self.sq_size, self.sq_size))
                        s.set_alpha(LAST_MOVE_COLOR[3])  # Use alpha from constant
                        s.fill(LAST_MOVE_COLOR[:3])  # Use RGB from constant
                        self.screen.blit(s, (x, y))

                # 2. HIGHLIGHT PREVIOUS DUCK POSITION
                if prev_duck_info and (r, c) == prev_duck_info:
                    s = pygame.Surface((self.sq_size, self.sq_size))
                    s.set_alpha(LAST_MOVE_COLOR[3])
                    s.fill(LAST_MOVE_COLOR[:3])
                    self.screen.blit(s, (x, y))

                # 3. SELECTION & VALID MOVES (Only Live)
                if is_live:
                    if self.selected_square == (r, c):
                        pygame.draw.rect(self.screen, HIGHLIGHT, (x, y, self.sq_size, self.sq_size))
                    if (r, c) in self.valid_moves:
                        s = pygame.Surface((self.sq_size, self.sq_size))
                        s.set_alpha(100)
                        s.fill((0, 255, 0))
                        self.screen.blit(s, (x, y))

                if draw_duck_pos == (r, c): self.draw_duck(r, c)

                piece = draw_board[r][c]
                if piece:
                    key = f"{piece.color}{piece.type}"
                    if key in self.scaled_images:
                        self.screen.blit(self.scaled_images[key], (x, y))
                    else:
                        text = UNICODE_PIECES[piece.color][piece.type]
                        col = (0, 0, 0) if piece.color == 'b' else (255, 255, 255)
                        surf = self.font_large.render(text, True, col)
                        rect = surf.get_rect(center=(x + self.sq_size // 2, y + self.sq_size // 2))
                        if piece.color == 'w':
                            outline = self.font_large.render(text, True, (0, 0, 0))
                            self.screen.blit(outline, outline.get_rect(center=(rect.centerx + 2, rect.centery + 2)))
                        self.screen.blit(surf, rect)

        # Draw UI Bar
        ui_y = self.screen_h - self.ui_height
        pygame.draw.rect(self.screen, BOARD_BG_COLOR, (0, ui_y, self.screen_w - self.panel_width, self.ui_height))

        status = f"WINNER: {self.winner}" if self.game_over else f"{'White' if self.turn == 'w' else 'Black'} | {'Move Piece' if self.phase == 'move_piece' else 'Place Duck'}"
        if not is_live: status = "VIEWING HISTORY (Go to end to play)"

        txt = self.font_ui.render(status, True, TEXT_COLOR)
        self.screen.blit(txt, (15, ui_y + 20))

        mouse = pygame.mouse.get_pos()
        btns = [("Menu", self.menu_btn_rect), ("Restart", self.restart_btn_rect)]
        if self.game_mode == 'pvp': btns.insert(1, ("Flip", self.flip_btn_rect))

        area_w = self.screen_w - self.panel_width - 250
        btn_w = 100
        start_x = self.screen_w - self.panel_width - (len(btns) * 110) - 10

        for i, (lbl, rect) in enumerate(btns):
            rect.width, rect.height = btn_w, 40
            rect.x, rect.centery = start_x + i * 110, ui_y + 30
            col = BUTTON_HOVER if rect.collidepoint(mouse) else BUTTON_COLOR
            pygame.draw.rect(self.screen, col, rect, border_radius=8)
            t = self.font_ui.render(lbl, True, (255, 255, 255))
            self.screen.blit(t, t.get_rect(center=rect.center))

        self.draw_history_panel()

    def draw_menu(self):
        self.screen.fill(MENU_BG)
        title = self.font_menu.render("DUCK CHESS", True, (255, 215, 0))
        self.screen.blit(title, title.get_rect(center=(self.screen_w // 2, self.screen_h * 0.2)))
        opts = [("Play as White", 'white_ai'), ("Play as Black", 'black_ai'), ("2 Player", 'pvp')]
        mouse = pygame.mouse.get_pos()
        for i, (text, mode) in enumerate(opts):
            rect = pygame.Rect(0, 0, 300, 60)
            rect.center = (self.screen_w // 2, self.screen_h * 0.4 + i * 80)
            col = BUTTON_HOVER if rect.collidepoint(mouse) else BUTTON_COLOR
            pygame.draw.rect(self.screen, col, rect, border_radius=10)
            t = self.font_ui.render(text, True, (255, 255, 255))
            self.screen.blit(t, t.get_rect(center=rect.center))
            if pygame.mouse.get_pressed()[0] and rect.collidepoint(mouse):
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