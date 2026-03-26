import pygame
import math
from DuckChess_Game.UI.settings import *


class BoardRenderingMixin:
    """Handles the rendering of the board, pieces, duck, and editor logic"""

    def _draw_base_board(self):
        """Helper to draw the 8x8 squares and the coordinates"""
        font_coord = pygame.font.SysFont("Arial", 12, bold=True)
        for r in range(8):
            for c in range(8):
                x, y = self.get_screen_pos(r, c)
                color = WHITE_COLOR if (r + c) % 2 == 0 else BLACK_SQ_COLOR
                pygame.draw.rect(self.screen, color, (x, y, self.sq_size, self.sq_size))

                text_color = WHITE_COLOR if (r + c) % 2 != 0 else BLACK_SQ_COLOR
                is_bottom_row = (r == 7) if self.player_side == 'w' else (r == 0)

                if is_bottom_row:
                    self.screen.blit(font_coord.render("abcdefgh"[c], True, text_color),
                                     (x + self.sq_size - 12, y + self.sq_size - 14))

                is_left_col = (c == 0) if self.player_side == 'w' else (c == 7)
                if is_left_col:
                    self.screen.blit(font_coord.render("87654321"[r], True, text_color), (x + 3, y + 2))

    def draw_duck(self, r, c):
        x, y = self.get_screen_pos(r, c)
        if 'duck' in self.scaled_images:
            img = self.scaled_images['duck']
            self.screen.blit(img,
                             (x + (self.sq_size - img.get_width()) // 2, y + (self.sq_size - img.get_height()) // 2))
        else:
            pygame.draw.circle(self.screen, (255, 220, 0), (x + self.sq_size // 2, y + self.sq_size // 2),
                               self.sq_size // 3)

    def draw_editor(self):
        self.draw_menu_background()

        # Draw Board Borders
        pygame.draw.rect(self.screen, (20, 20, 20),
                         (self.board_x - 2, self.board_y - 2, self.sq_size * 8 + 4, self.sq_size * 8 + 4), width=2)

        self._draw_base_board()

        for r in range(8):
            for c in range(8):
                if self.duck_pos == (r, c):
                    self.draw_duck(r, c)
                p = self.board[r][c]
                if p:
                    x, y = self.get_screen_pos(r, c)
                    self._draw_piece_sprite(p, x, y)

        # Draw Palette (Side Panel)
        palette_x = self.board_x + self.sq_size * 8 + 40
        start_y = self.board_y
        white_pieces = [KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN]

        for i, p_type in enumerate(white_pieces):
            y = start_y + i * (self.sq_size + 10)
            key = f"w{p_type}"
            if key in self.scaled_images:
                r_rect = pygame.Rect(palette_x, y, self.sq_size, self.sq_size)
                if r_rect.collidepoint(pygame.mouse.get_pos()):
                    pygame.draw.rect(self.screen, (255, 255, 255, 50), r_rect)
                self.screen.blit(self.scaled_images[key], (palette_x, y))

        for i, p_type in enumerate(white_pieces):
            y = start_y + i * (self.sq_size + 10)
            key = f"b{p_type}"
            if key in self.scaled_images:
                r_rect = pygame.Rect(palette_x + self.sq_size + 10, y, self.sq_size, self.sq_size)
                if r_rect.collidepoint(pygame.mouse.get_pos()):
                    pygame.draw.rect(self.screen, (255, 255, 255, 50), r_rect)
                self.screen.blit(self.scaled_images[key], (palette_x + self.sq_size + 10, y))

        y_misc = start_y + 6 * (self.sq_size + 10)
        if 'duck' in self.scaled_images:
            self.screen.blit(self.scaled_images['duck'], (palette_x, y_misc))

        trash_rect = pygame.Rect(palette_x + self.sq_size + 10, y_misc, self.sq_size, self.sq_size)
        pygame.draw.rect(self.screen, (200, 50, 50), trash_rect, border_radius=4)
        trash_txt = self.font_ui.render("CLR", True, (255, 255, 255))
        self.screen.blit(trash_txt, trash_txt.get_rect(center=trash_rect.center))

        # Floating Piece (Dragging)
        if hasattr(self, 'dragging') and self.dragging and self.drag_piece:
            mx, my = pygame.mouse.get_pos()
            key = self.drag_piece
            if key == 'duck' and 'duck' in self.scaled_images:
                self.screen.blit(self.scaled_images['duck'], (mx - self.sq_size // 2, my - self.sq_size // 2))
            elif key in self.scaled_images:
                self.screen.blit(self.scaled_images[key], (mx - self.sq_size // 2, my - self.sq_size // 2))

        # UI Controls
        hud_rect = pygame.Rect(20, self.screen_h - 70, self.screen_w - 40, 60)
        self.draw_glass_panel(hud_rect)

        valid = self.validate_editor_board()
        status_txt = "EDITOR MODE" if not valid else "EDITOR MODE: Ready"
        col = (200, 50, 50) if not valid else (50, 200, 50)
        self.screen.blit(self.font_status.render(status_txt, True, col), (40, self.screen_h - 50))

        mouse = pygame.mouse.get_pos()
        self.editor_turn_btn = pygame.Rect(self.screen_w - 560, self.screen_h - 58, 140, 36)
        is_white = (self.turn == 'w')
        btn_col = EVAL_WHITE if is_white else EVAL_BLACK
        txt_col = (0, 0, 0) if is_white else (255, 255, 255)

        pygame.draw.rect(self.screen, btn_col, self.editor_turn_btn, border_radius=6)
        pygame.draw.rect(self.screen, BTN_BORDER, self.editor_turn_btn, width=1, border_radius=6)
        t_surf = self.font_ui.render("Turn: WHITE" if is_white else "Turn: BLACK", True, txt_col)
        self.screen.blit(t_surf, t_surf.get_rect(center=self.editor_turn_btn.center))

        self.editor_menu_btn = pygame.Rect(self.screen_w - 410, self.screen_h - 58, 120, 36)
        self.draw_styled_button(self.editor_menu_btn, "MENU", self.editor_menu_btn.collidepoint(mouse))

        self.editor_clear_btn = pygame.Rect(self.screen_w - 280, self.screen_h - 58, 120, 36)
        self.draw_styled_button(self.editor_clear_btn, "CLEAR ALL", self.editor_clear_btn.collidepoint(mouse))

        self.editor_play_btn = pygame.Rect(self.screen_w - 150, self.screen_h - 58, 120, 36)
        if valid:
            self.draw_styled_button(self.editor_play_btn, "PLAY", self.editor_play_btn.collidepoint(mouse))

    def draw_game(self, hidden_square=None):
        self.draw_menu_background()

        is_live = (self.view_index == len(self.history) - 1)
        if is_live:
            board, d_pos, last_mv, prev_d = self.board, self.duck_pos, self.last_move_arrow, self.prev_duck_pos
        else:
            snap = self.history[self.view_index]
            board, d_pos, last_mv, prev_d = snap['board'], snap['duck_pos'], snap['last_move'], snap['prev_duck']

        hide_pos = self.drag_start if hasattr(self,
                                              'dragging') and self.dragging and self.drag_start and is_live else hidden_square

        # Board Border
        border_rect = pygame.Rect(self.board_x - 20, self.board_y - 20, self.sq_size * 8 + 40, self.sq_size * 8 + 40)
        pygame.draw.rect(self.screen, BTN_BORDER, border_rect, width=0, border_radius=4)
        pygame.draw.rect(self.screen, (20, 20, 20),
                         (self.board_x - 2, self.board_y - 2, self.sq_size * 8 + 4, self.sq_size * 8 + 4), width=2)

        self._draw_base_board()

        for r in range(8):
            for c in range(8):
                # Highlights: Last Move & Previous Duck Position
                if last_mv and ((r, c) == last_mv[0] or (r, c) == last_mv[1]):
                    self._draw_highlight_square(r, c, LAST_MOVE_COLOR)
                if prev_d and (r, c) == prev_d:
                    self._draw_highlight_square(r, c, LAST_MOVE_COLOR)

                if is_live and not self.promotion_pending:
                    x, y = self.get_screen_pos(r, c)
                    if self.phase == 'move_piece':
                        if self.selected_square == (r, c):
                            pygame.draw.rect(self.screen, HIGHLIGHT, (x, y, self.sq_size, self.sq_size))
                        if (r, c) in self.valid_moves:
                            s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
                            if board[r][c]:
                                pygame.draw.circle(s, (100, 255, 100, 180), (self.sq_size // 2, self.sq_size // 2),
                                                   self.sq_size // 2 - 2, 6)
                            else:
                                pygame.draw.circle(s, (100, 255, 100, 150), (self.sq_size // 2, self.sq_size // 2),
                                                   self.sq_size // 6)
                            self.screen.blit(s, (x, y))
                    elif self.phase == 'move_duck':
                        if board[r][c] is None and (r, c) != prev_d:
                            s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
                            pygame.draw.circle(s, (255, 215, 0, 100), (self.sq_size // 2, self.sq_size // 2),
                                               self.sq_size // 5)
                            self.screen.blit(s, (x, y))

                if hide_pos and (r, c) == hide_pos:
                    continue

                if d_pos == (r, c):
                    self.draw_duck(r, c)

                p = board[r][c]
                if p:
                    if p.type == 'K' and self.is_in_check(p.color, board):
                        self._draw_highlight_square(r, c, (235, 60, 60, 180))

                    x, y = self.get_screen_pos(r, c)
                    self._draw_piece_sprite(p, x, y)

        if hasattr(self, 'dragging') and self.dragging and self.drag_piece and is_live:
            mx, my = pygame.mouse.get_pos()
            draw_x, draw_y = mx - self.drag_offset[0], my - self.drag_offset[1]
            key = 'duck' if self.drag_piece == 'duck' else f"{self.drag_piece.color}{self.drag_piece.type}"
            if key in self.scaled_images:
                self.screen.blit(self.scaled_images[key], (draw_x, draw_y))

        if self.show_eval:
            self.draw_eval_bar(board)

        self.draw_history_panel()

        # HUD Rendering
        hud_rect = pygame.Rect(20, self.screen_h - 70, self.screen_w - self.panel_width - 40, 60)
        self.draw_glass_panel(hud_rect)

        if self.game_over:
            status, status_col = ("GAME OVER: DRAW", (200, 200, 200)) if self.winner == 'draw' else (
            f"WINNER: {'WHITE' if self.winner == 'w' else 'BLACK'}", MENU_ACCENT)
        elif not is_live:
            status, status_col = "VIEWING HISTORY", (200, 200, 255)
        elif self.promotion_pending:
            status, status_col = "CHOOSE PROMOTION PIECE", MENU_ACCENT
        else:
            status, status_col = f"{'WHITE' if self.turn == 'w' else 'BLACK'} TO {'MOVE PIECE' if self.phase == 'move_piece' else 'PLACE DUCK'}", (
            220, 220, 220)

        self.screen.blit(self.font_status.render(status, True, status_col), (40, self.screen_h - 50))

        mouse = pygame.mouse.get_pos()
        btns = [
            ("Menu", self.menu_btn_rect),
            ("Hide Eval" if self.show_eval else "Show Eval", self.eval_btn_rect),
            ("Restart", self.restart_btn_rect)
        ]
        if self.game_mode == 'pvp':
            btns.insert(2, ("Flip Board", self.flip_btn_rect))

        start_x = hud_rect.right - 20 - (len(btns) * 110)
        for i, (lbl, r) in enumerate(btns):
            r.width, r.height, r.x, r.centery = 100, 36, start_x + i * 110, hud_rect.centery
            self.draw_styled_button(r, lbl, r.collidepoint(mouse))

        if self.promotion_pending and is_live:
            self.draw_promotion_ui()

    def animate_move_visual(self, start, end, piece, is_duck=False):
        if self.view_index != len(self.history) - 1:
            return

        x1, y1 = self.get_screen_pos(start[0], start[1])
        x2, y2 = self.get_screen_pos(end[0], end[1])

        key = 'duck' if is_duck else f"{piece.color}{piece.type}"
        img = self.scaled_images.get(key)
        if not img and not is_duck:
            return

        start_time = pygame.time.get_ticks()
        clock = pygame.time.Clock()

        while True:
            now = pygame.time.get_ticks()
            elapsed = now - start_time
            if elapsed >= ANIMATION_SPEED:
                break

            progress = 1 - math.pow(1 - (elapsed / ANIMATION_SPEED), 3)
            current_x = x1 + (x2 - x1) * progress
            current_y = y1 + (y2 - y1) * progress

            self.draw_game(hidden_square=start)
            if img: self.screen.blit(img, (current_x, current_y))
            pygame.display.flip()
            clock.tick(ANIMATION_FPS)