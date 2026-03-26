import pygame
from DuckChess_Game.UI.settings import *


class UIRenderingMixin:
    """Handles UI components: Menus, History Panel, Eval Bar, and Buttons"""

    def draw_menu_background(self):
        tile_size = 100
        cols, rows = self.screen_w // tile_size + 1, self.screen_h // tile_size + 1
        for r in range(rows):
            for c in range(cols):
                color = MENU_BG_DARK if (r + c) % 2 == 0 else MENU_BG_LIGHT
                pygame.draw.rect(self.screen, color, (c * tile_size, r * tile_size, tile_size, tile_size))

    def draw_glass_panel(self, rect):
        s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        s.fill((20, 25, 30, 230))
        self.screen.blit(s, rect.topleft)
        pygame.draw.rect(self.screen, BTN_BORDER, rect, width=1, border_radius=8)

    def draw_styled_button(self, rect, text, hover, font=None):
        if font is None:
            font = self.font_menu_sub

        color = BTN_HOVER if hover else BTN_NORMAL
        border_col = MENU_ACCENT if hover else BTN_BORDER

        shadow_rect = rect.copy()
        shadow_rect.y += 2
        pygame.draw.rect(self.screen, (0, 0, 0, 100), shadow_rect, border_radius=6)
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        pygame.draw.rect(self.screen, border_col, rect, width=1, border_radius=6)

        txt_col = MENU_ACCENT if hover else BTN_TEXT
        txt_surf = font.render(text, True, txt_col)
        self.screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

    def draw_menu(self):
        self.draw_menu_background()

        t_shadow = self.font_menu_title.render("DUCK CHESS", True, (0, 0, 0))
        self.screen.blit(t_shadow, t_shadow.get_rect(center=(self.screen_w // 2 + 3, self.screen_h * 0.2 + 3)))
        t_main = self.font_menu_title.render("DUCK CHESS", True, MENU_ACCENT)
        self.screen.blit(t_main, t_main.get_rect(center=(self.screen_w // 2, self.screen_h * 0.2)))

        panel_rect = pygame.Rect((self.screen_w - 400) // 2, (self.screen_h - 400) // 2 + 40, 400, 400)
        self.draw_glass_panel(panel_rect)

        opts = [
            ("Play as White", 'white_ai'),
            ("Play as Black", 'black_ai'),
            ("2 Player (PvP)", 'pvp'),
            ("Edit Board", 'edit'),
            ("Load Replay", 'load_replay')
        ]

        mouse = pygame.mouse.get_pos()
        click = pygame.mouse.get_pressed()[0]

        for i, (txt, mode) in enumerate(opts):
            # Make buttons slightly smaller to fit 5 options nicely
            r = pygame.Rect(0, 0, 300, 50)
            r.centerx, r.top = self.screen_w // 2, panel_rect.top + 30 + i * 70
            self.draw_styled_button(r, txt, r.collidepoint(mouse))

            if click and r.collidepoint(mouse):
                pygame.time.wait(150)

                if mode == 'edit':
                    self.state = 'edit'
                    self.reset_game_state()
                    self.clear_board()
                    self.init_board()
                elif mode == 'load_replay':
                    # Open a native OS file dialog to select the .pkl file
                    import tkinter as tk
                    from tkinter import filedialog

                    root = tk.Tk()
                    root.wm_attributes('-topmost', 1)  # Keep dialog above PyGame
                    root.withdraw()  # Hide the empty root window

                    filepath = filedialog.askopenfilename(
                        title="Select Duck Chess Replay",
                        filetypes=[("Replay Files", "*.pkl")]
                    )
                    root.destroy()

                    if filepath:
                        self.load_replay_file(filepath)
                else:
                    self.game_mode = mode
                    self.player_side = 'b' if mode == 'black_ai' else 'w'
                    self.state = 'game'
                    self.reset_game_state()
                return

    def draw_eval_bar(self, current_board):
        if self.game_over:
            self.target_eval_score = 0 if self.winner == 'draw' else (20 if self.winner == 'w' else -20)
        else:
            self.target_eval_score = self.calculate_material_score(current_board)

        diff = self.target_eval_score - self.current_eval_score
        if abs(diff) < 0.05:
            self.current_eval_score = self.target_eval_score
        else:
            self.current_eval_score += diff * 0.1

        max_adv = 20
        normalized = (max(-max_adv, min(max_adv, self.current_eval_score)) + max_adv) / (2 * max_adv)
        bar_h, bar_y, bar_x, bar_w = self.sq_size * 8, self.board_y, self.eval_bar_x, self.eval_bar_width

        pygame.draw.rect(self.screen, BTN_BORDER, (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=4)
        mid_y = bar_y + bar_h * (1 - normalized)
        pygame.draw.rect(self.screen, EVAL_BLACK, (bar_x, bar_y, bar_w, mid_y - bar_y))
        pygame.draw.rect(self.screen, EVAL_WHITE, (bar_x, mid_y, bar_w, bar_y + bar_h - mid_y))

        if self.game_over:
            color = (150, 150, 150)
            if self.winner == 'w':
                color = EVAL_WHITE
            elif self.winner == 'b':
                color = EVAL_BLACK
            pygame.draw.rect(self.screen, color, (bar_x, bar_y, bar_w, bar_h))

        score_txt = f"{abs(int(round(self.current_eval_score)))}"
        txt_surf = self.font_eval.render(score_txt, True, TEXT_COLOR if normalized > 0.95 else EVAL_WHITE)
        self.screen.blit(txt_surf, txt_surf.get_rect(center=(bar_x + bar_w // 2, bar_y + 15)))

    def draw_history_panel(self):
        self.draw_glass_panel(pygame.Rect(self.screen_w - self.panel_width, 0, self.panel_width, self.screen_h))
        title = self.font_status.render("Move History", True, MENU_ACCENT)
        self.screen.blit(title, (self.screen_w - self.panel_width + 15, 15))

        counter = self.font_ui.render(f"{self.view_index} / {len(self.history) - 1}", True, (150, 150, 150))
        self.screen.blit(counter, (self.screen_w - 90, 18))
        pygame.draw.line(self.screen, BTN_BORDER, (self.screen_w - self.panel_width + 10, 45), (self.screen_w - 10, 45))

        full_log = self.history[-1]['log']
        start_y = 55
        line_height = 24
        col_white_x = self.screen_w - self.panel_width + 10
        col_black_x = self.screen_w - self.panel_width + 155

        available_height = self.nav_btns['start'].top - start_y - 10
        max_rows = available_height // line_height
        total_rows = (len(full_log) + 1) // 2

        current_ply_idx = self.view_index - 1
        current_row_idx = current_ply_idx // 2
        scroll_row = max(0, current_row_idx - (max_rows - 2)) if current_row_idx > max_rows - 2 else 0

        for row in range(scroll_row, min(total_rows, scroll_row + max_rows)):
            y_pos = start_y + (row - scroll_row) * line_height

            # White Move
            w_idx = row * 2
            if w_idx < len(full_log):
                is_active = (w_idx == current_ply_idx)
                if is_active:
                    pygame.draw.rect(self.screen, BTN_NORMAL, pygame.Rect(col_white_x - 2, y_pos, 140, line_height),
                                     border_radius=4)
                color = MENU_ACCENT if is_active else (220, 220, 220)
                self.screen.blit(self.font_history.render(full_log[w_idx], True, color), (col_white_x, y_pos + 4))

            # Black Move
            b_idx = row * 2 + 1
            if b_idx < len(full_log):
                raw_str = full_log[b_idx]
                clean_str = raw_str.split(' ', 1)[1] if "..." in raw_str and len(raw_str.split(' ', 1)) > 1 else raw_str

                is_active = (b_idx == current_ply_idx)
                if is_active:
                    pygame.draw.rect(self.screen, BTN_NORMAL, pygame.Rect(col_black_x - 2, y_pos, 140, line_height),
                                     border_radius=4)
                color = MENU_ACCENT if is_active else (220, 220, 220)
                self.screen.blit(self.font_history.render(clean_str, True, color), (col_black_x, y_pos + 4))

        mouse = pygame.mouse.get_pos()
        for lbl, key in [("<<", 'start'), ("<", 'prev'), (">", 'next'), (">>", 'end')]:
            self.draw_styled_button(self.nav_btns[key], lbl, self.nav_btns[key].collidepoint(mouse), self.font_nav)

    def get_promotion_rects(self):
        if not self.promotion_coords:
            return []
        r, c = self.promotion_coords
        bx, by = self.get_screen_pos(r, c)

        opts = [QUEEN, ROOK, BISHOP, KNIGHT]
        menu_h = self.sq_size * len(opts)
        start_y = by + (self.sq_size - menu_h) // 2
        board_top, board_bottom = self.board_y, self.board_y + self.sq_size * 8

        if start_y < board_top:
            start_y = board_top
        elif start_y + menu_h > board_bottom:
            start_y = board_bottom - menu_h

        return [(pygame.Rect(bx, start_y + i * self.sq_size, self.sq_size, self.sq_size), p) for i, p in
                enumerate(opts)]

    def draw_promotion_ui(self):
        rects = self.get_promotion_rects()
        if not rects:
            return
        container = rects[0][0].unionall([r[0] for r in rects])
        pygame.draw.rect(self.screen, EVAL_WHITE, container)
        pygame.draw.rect(self.screen, BTN_BORDER, container, width=2)

        m = pygame.mouse.get_pos()
        for r, p in rects:
            if r.collidepoint(m): pygame.draw.rect(self.screen, HIGHLIGHT, r)
            k = f"{self.turn}{p}"
            if k in self.scaled_images: self.screen.blit(self.scaled_images[k], r)