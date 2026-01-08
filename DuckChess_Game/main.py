import pygame
import sys
import copy
import asyncio
from settings import *
from logic import GameLogicMixin
from rendering import RenderingMixin
from pieces import Piece


class DuckChess(GameLogicMixin, RenderingMixin):
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Duck Chess: Final Pro Edition")
        self.clock = pygame.time.Clock()

        self.game_mode = None
        self.player_side = 'w'
        self.state = 'menu'  # Start in Menu

        # Initialize AI
        self.init_ai()

        # Layout
        self.sq_size = 0
        self.board_x = 0
        self.board_y = 0
        self.ui_height = 60
        self.panel_width = 300
        self.eval_bar_width = 36
        self.side_margin = 20

        # Buttons (Initialized to zero, updated in resize_layout)
        self.nav_btns = {k: pygame.Rect(0, 0, 0, 0) for k in ['start', 'prev', 'next', 'end']}
        self.menu_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.flip_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.restart_btn_rect = pygame.Rect(0, 0, 0, 0)

        # --- NEW: Eval Toggle ---
        self.show_eval = True  # Default is ON
        self.eval_btn_rect = pygame.Rect(0, 0, 0, 0)

        # Editor Buttons (Initialized to zero)
        self.editor_play_btn = pygame.Rect(0, 0, 0, 0)
        self.editor_clear_btn = pygame.Rect(0, 0, 0, 0)
        self.editor_menu_btn = pygame.Rect(0, 0, 0, 0)
        self.editor_turn_btn = pygame.Rect(0, 0, 0, 0)

        # Assets
        self.original_images = {}
        self.scaled_images = {}
        self.sounds = {}
        self.load_assets()

        # State Variables
        self.move_log = []
        self.current_move_str = ""
        self.turn_number = 1
        self.history = []
        self.view_index = -1

        # Drag & Drop State
        self.dragging = False
        self.drag_piece = None
        self.drag_start = None
        self.drag_offset = (0, 0)

        # Promotion Specific
        self.promotion_pending = False
        self.promotion_coords = None

        self.target_eval_score = 0
        self.current_eval_score = 0.0

        self.resize_layout(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.reset_game_state()

    def save_snapshot(self):
        self.history.append({
            'board': copy.deepcopy(self.board),
            'duck_pos': self.duck_pos,
            'prev_duck': self.prev_duck_pos,
            'last_move': self.last_move_arrow,
            'captured': copy.deepcopy(self.captured),
            'log': list(self.move_log)
        })
        self.view_index = len(self.history) - 1

    def reset_game_state(self):
        self.board = [[None] * 8 for _ in range(8)]

        # 1. Board Setup
        # Only init standard board if NOT coming from editor with custom setup
        if self.state != 'game':
            self.init_board()

        if self.state == 'menu':
            self.init_board()
        elif self.state == 'game' and self.game_mode != 'pvp':
            self.init_board()
        elif self.state == 'game' and not self.history:
            # Fresh start check
            if not any(any(row) for row in self.board):
                self.init_board()

        # 2. Duck & Logic Initialization (The Fix)
        # Ensure variables exist first to prevent AttributeErrors
        if not hasattr(self, 'duck_pos'):
            self.duck_pos = (-1, -1)
            self.prev_duck_pos = (-1, -1)

        # If we are NOT in edit mode, we generally want to reset the duck
        if self.state != 'edit':
            self.duck_pos = (-1, -1)
            self.prev_duck_pos = (-1, -1)

        if self.state != 'game':
            self.turn = 'w'

        self.phase = 'move_piece'
        self.selected_square = None
        self.valid_moves = []
        self.game_over = False
        self.winner = None
        self.en_passant_target = None
        self.half_move_clock = 0
        self.rep_history = {}

        self.move_log = []
        self.last_move_arrow = None
        self.turn_number = 1
        self.current_move_str = ""
        self.history = []

        self.captured = {'w': [], 'b': []}

        self.promotion_pending = False
        self.target_eval_score = 0
        self.current_eval_score = 0.0

        if self.game_mode == 'black_ai':
            self.waiting_for_ai = True
            self.ai_wait_start = pygame.time.get_ticks()
        else:
            self.waiting_for_ai = False

        # Save initial state
        self.save_snapshot()
    def handle_mouse_down(self, pos):
        if self.promotion_pending: return

        # Navigation
        if self.nav_btns['start'].collidepoint(pos): self.view_index = 0; return
        if self.nav_btns['prev'].collidepoint(pos): self.view_index = max(0, self.view_index - 1); return
        if self.nav_btns['next'].collidepoint(pos): self.view_index = min(len(self.history) - 1,
                                                                          self.view_index + 1); return
        if self.nav_btns['end'].collidepoint(pos): self.view_index = len(self.history) - 1; return

        # Control Buttons
        if self.restart_btn_rect.collidepoint(pos):
            self.init_board()  # Force standard reset
            self.reset_game_state()
            return
        # --- NEW: Eval Toggle Click ---
        if self.eval_btn_rect.collidepoint(pos):
            self.show_eval = not self.show_eval
            return
        if self.menu_btn_rect.collidepoint(pos): self.state = 'menu'; return
        if self.game_mode == 'pvp' and self.flip_btn_rect.collidepoint(pos):
            self.player_side = 'b' if self.player_side == 'w' else 'w';
            return

        is_live = (self.view_index == len(self.history) - 1)
        if not is_live or self.game_over or self.waiting_for_ai: return

        r, c = self.get_board_pos(pos[0], pos[1])
        if r == -1: return

        if self.phase == 'move_piece':
            piece = self.board[r][c]

            if piece and piece.color == self.turn:
                self.dragging = True
                self.drag_piece = piece
                self.drag_start = (r, c)
                px, py = self.get_screen_pos(r, c)
                self.drag_offset = (pos[0] - px, pos[1] - py)
                self.selected_square = (r, c)
                self.valid_moves = self.get_piece_legal_moves(r, c)

            elif self.selected_square and (r, c) in self.valid_moves:
                self.execute_move(self.selected_square, (r, c))
                self.selected_square = None
                self.valid_moves = []

            else:
                self.selected_square = None
                self.valid_moves = []

        elif self.phase == 'move_duck':
            if (r, c) == self.duck_pos:
                self.dragging = True
                self.drag_piece = 'duck'
                self.drag_start = (r, c)
                px, py = self.get_screen_pos(r, c)
                self.drag_offset = (pos[0] - px, pos[1] - py)

            elif not self.board[r][c] and (r, c) != self.prev_duck_pos:
                self.place_duck((r, c))

    def handle_mouse_up(self, pos):
        if not self.dragging: return

        r, c = self.get_board_pos(pos[0], pos[1])

        if r != -1:
            if self.phase == 'move_piece' and self.drag_piece != 'duck':
                if (r, c) in self.valid_moves:
                    self.execute_move(self.drag_start, (r, c), animated=False)
                    self.selected_square = None
                    self.valid_moves = []
                elif (r, c) == self.drag_start:
                    pass
                else:
                    self.selected_square = None
                    self.valid_moves = []

            elif self.phase == 'move_duck' and self.drag_piece == 'duck':
                if not self.board[r][c] and (r, c) != self.prev_duck_pos:
                    self.place_duck((r, c), animated=False)

        self.dragging = False
        self.drag_piece = None
        self.drag_start = None

    def handle_keyboard(self, event):
        if event.key == pygame.K_LEFT:
            self.view_index = max(0, self.view_index - 1)
        elif event.key == pygame.K_RIGHT:
            self.view_index = min(len(self.history) - 1, self.view_index + 1)

    def handle_editor_input(self, event):
        mx, my = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            # --- Turn Toggle ---
            if hasattr(self, 'editor_turn_btn') and self.editor_turn_btn.collidepoint((mx, my)):
                self.turn = 'b' if self.turn == 'w' else 'w'
                return

            # --- UI Buttons ---
            if hasattr(self, 'editor_play_btn') and self.editor_play_btn.collidepoint((mx, my)):
                if self.validate_editor_board():
                    self.state = 'game'
                    self.game_mode = 'pvp'
                    self.phase = 'move_piece'
                    self.save_snapshot()
                    return

            if hasattr(self, 'editor_clear_btn') and self.editor_clear_btn.collidepoint((mx, my)):
                self.clear_board()
                return

            if hasattr(self, 'editor_menu_btn') and self.editor_menu_btn.collidepoint((mx, my)):
                self.state = 'menu'
                return

            # --- Palette Interaction ---
            palette_x = self.board_x + self.sq_size * 8 + 40
            start_y = self.board_y
            white_pieces = [KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN]

            # White Column
            for i, p_type in enumerate(white_pieces):
                r = pygame.Rect(palette_x, start_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
                if r.collidepoint((mx, my)):
                    self.dragging = True
                    self.drag_piece = f"w{p_type}"
                    return

            # Black Column
            for i, p_type in enumerate(white_pieces):
                r = pygame.Rect(palette_x + self.sq_size + 10, start_y + i * (self.sq_size + 10), self.sq_size,
                                self.sq_size)
                if r.collidepoint((mx, my)):
                    self.dragging = True
                    self.drag_piece = f"b{p_type}"
                    return

            # Duck
            y_duck = start_y + 6 * (self.sq_size + 10)
            r_duck = pygame.Rect(palette_x, y_duck, self.sq_size, self.sq_size)
            if r_duck.collidepoint((mx, my)):
                self.dragging = True
                self.drag_piece = "duck"
                return

            # --- Board Interaction ---
            r, c = self.get_board_pos(mx, my)
            if r != -1:
                p = self.board[r][c]
                if self.duck_pos == (r, c):
                    self.dragging = True
                    self.drag_piece = "duck"
                    self.duck_pos = (-1, -1)
                elif p:
                    self.dragging = True
                    self.drag_piece = f"{p.color}{p.type}"
                    self.board[r][c] = None

        elif event.type == pygame.MOUSEBUTTONUP:
            if self.dragging:
                r, c = self.get_board_pos(mx, my)
                if r != -1:
                    if self.drag_piece == 'duck':
                        self.duck_pos = (r, c)
                        self.board[r][c] = None
                    else:
                        color = self.drag_piece[0]
                        ptype = self.drag_piece[1:]
                        self.board[r][c] = Piece(color, ptype)
                        if self.duck_pos == (r, c): self.duck_pos = (-1, -1)
                self.dragging = False
                self.drag_piece = None

    # --- ASYNC MAIN LOOP ---
    async def run(self):
        while True:
            # 1. EVENT HANDLING
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.VIDEORESIZE:
                    self.resize_layout(event.w, event.h)

                if self.state == 'menu':
                    pass

                elif self.state == 'edit':
                    self.handle_editor_input(event)

                elif self.state == 'game':
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if self.promotion_pending:
                            for rect, p_type in self.get_promotion_rects():
                                if rect.collidepoint(event.pos):
                                    self.promote_pawn(p_type)
                        else:
                            self.handle_mouse_down(event.pos)

                    elif event.type == pygame.MOUSEBUTTONUP:
                        self.handle_mouse_up(event.pos)

                    elif event.type == pygame.KEYDOWN:
                        self.handle_keyboard(event)

            # 2. DRAWING & LOGIC
            if self.state == 'menu':
                self.draw_menu()

            elif self.state == 'edit':
                self.draw_editor()

            else:  # Game Mode
                self.ai_turn()
                self.draw_game()

            # 3. REFRESH
            pygame.display.flip()
            self.clock.tick(FPS)
            await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(DuckChess().run())