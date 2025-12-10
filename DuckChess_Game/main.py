import pygame
import sys
import copy
from settings import *
from logic import GameLogicMixin
from rendering import RenderingMixin


class DuckChess(GameLogicMixin, RenderingMixin):
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Duck Chess: Final Pro Edition")
        self.clock = pygame.time.Clock()

        self.game_mode = None
        self.player_side = 'w'
        self.state = 'menu'

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

        # Buttons
        self.nav_btns = {k: pygame.Rect(0, 0, 0, 0) for k in ['start', 'prev', 'next', 'end']}
        self.menu_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.flip_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.restart_btn_rect = pygame.Rect(0, 0, 0, 0)

        # Assets
        self.original_images = {}
        self.scaled_images = {}
        self.sounds = {}  # Init sound dict
        self.load_assets()

        # State Variables
        self.move_log = []
        self.current_move_str = ""
        self.turn_number = 1
        self.history = []
        self.view_index = -1

        # Drag & Drop State
        self.dragging = False
        self.drag_piece = None  # The piece object or 'duck' string
        self.drag_start = None  # (r, c)
        self.drag_offset = (0, 0)  # Offset from mouse to piece top-left

        # Promotion Specific
        self.promotion_pending = False
        self.promotion_coords = None
        self.promotion_options = []

        # Eval Animation
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

        # State tracking
        self.move_log = []
        self.last_move_arrow = None
        self.turn_number = 1
        self.current_move_str = ""
        self.history = []

        # Initialize captured list to prevent crashes in logic.py
        self.captured = {'w': [], 'b': []}

        self.promotion_pending = False
        self.target_eval_score = 0
        self.current_eval_score = 0.0

        # --- FIX: Check if AI needs to move immediately ---
        # If I am playing as Black ('black_ai'), AI is White ('w').
        # Since White moves first, AI must start.
        if self.game_mode == 'black_ai':
            self.waiting_for_ai = True
            self.ai_wait_start = pygame.time.get_ticks()
        else:
            self.waiting_for_ai = False
        # --------------------------------------------------

        self.save_snapshot()
    def handle_mouse_down(self, pos):
        # 1. UI Interactions (Priority)
        if self.promotion_pending: return  # Handled in loop or specific click
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

        # 2. Game Interaction Check
        is_live = (self.view_index == len(self.history) - 1)
        if not is_live or self.game_over or self.waiting_for_ai: return

        # 3. Board Click Logic
        r, c = self.get_board_pos(pos[0], pos[1])
        if r == -1: return  # Clicked outside board

        # --- Phase: Move Piece ---
        if self.phase == 'move_piece':
            piece = self.board[r][c]

            # A. Clicked Own Piece -> Start Drag & Select
            if piece and piece.color == self.turn:
                self.dragging = True
                self.drag_piece = piece
                self.drag_start = (r, c)

                # Calculate offset for smooth dragging
                px, py = self.get_screen_pos(r, c)
                self.drag_offset = (pos[0] - px, pos[1] - py)

                self.selected_square = (r, c)
                self.valid_moves = self.get_piece_legal_moves(r, c)

            # B. Clicked Valid Move (Click-Click method)
            elif self.selected_square and (r, c) in self.valid_moves:
                self.execute_move(self.selected_square, (r, c))
                self.selected_square = None
                self.valid_moves = []

            # C. Clicked Empty/Enemy (Deselect)
            else:
                self.selected_square = None
                self.valid_moves = []

        # --- Phase: Move Duck ---
        elif self.phase == 'move_duck':
            # A. Drag existing duck
            if (r, c) == self.duck_pos:
                self.dragging = True
                self.drag_piece = 'duck'
                self.drag_start = (r, c)
                px, py = self.get_screen_pos(r, c)
                self.drag_offset = (pos[0] - px, pos[1] - py)

            # B. Place duck (Click method)
            elif not self.board[r][c] and (r, c) != self.prev_duck_pos:
                self.place_duck((r, c))

    def handle_mouse_up(self, pos):
        if not self.dragging: return

        # Drop Logic
        r, c = self.get_board_pos(pos[0], pos[1])

        # Valid drop?
        if r != -1:
            if self.phase == 'move_piece' and self.drag_piece != 'duck':
                # If dropped on a valid square
                if (r, c) in self.valid_moves:
                    # FIX: animated=False ensures it snaps instantly
                    self.execute_move(self.drag_start, (r, c), animated=False)
                    self.selected_square = None
                    self.valid_moves = []
                # If dropped on start square, keep selection (treat as click)
                elif (r, c) == self.drag_start:
                    pass
                    # Invalid drop
                else:
                    self.selected_square = None
                    self.valid_moves = []

            elif self.phase == 'move_duck' and self.drag_piece == 'duck':
                if not self.board[r][c] and (r, c) != self.prev_duck_pos:
                    # FIX: animated=False
                    self.place_duck((r, c), animated=False)

        # Reset Drag
        self.dragging = False
        self.drag_piece = None
        self.drag_start = None
    def handle_keyboard(self, event):
        if event.key == pygame.K_LEFT:
            self.view_index = max(0, self.view_index - 1)
        elif event.key == pygame.K_RIGHT:
            self.view_index = min(len(self.history) - 1, self.view_index + 1)

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                if event.type == pygame.VIDEORESIZE: self.resize_layout(event.w, event.h)

                # Input Handling
                if self.state == 'game':
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if self.promotion_pending:
                            # Special case for promotion click
                            for rect, p_type in self.get_promotion_rects():
                                if rect.collidepoint(event.pos): self.promote_pawn(p_type)
                        else:
                            self.handle_mouse_down(event.pos)

                    elif event.type == pygame.MOUSEBUTTONUP:
                        self.handle_mouse_up(event.pos)

                    elif event.type == pygame.KEYDOWN:
                        self.handle_keyboard(event)

            if self.state == 'menu':
                self.draw_menu()
            else:
                self.ai_turn()
                self.draw_game()
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    DuckChess().run()