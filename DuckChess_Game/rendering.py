import pygame
import os
import math
from settings import *


class RenderingMixin:
    """Handles Assets, Drawing, Audio, and Layout"""

    def load_assets(self):
        # 1. Paths
        base_path = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.normpath(os.path.join(base_path, "..", "assets"))
        pieces_dir = os.path.join(assets_dir, "pieces")
        sounds_dir = os.path.join(assets_dir, "sounds")

        # 2. Init Sound System
        try:
            pygame.mixer.init()
            self.sounds = {}
        except Exception as e:
            print(f"Sound init failed: {e}")
            self.sounds = {}

        # 3. Load Sounds
        sound_files = {
            'move': 'move.wav',
            'capture': 'capture.wav',
            'castle': 'castle.wav',
            'promote': 'promote.wav',
            'notify': 'notify.wav',
            'game_over': 'game_over.wav'
        }

        if os.path.exists(sounds_dir):
            for name, filename in sound_files.items():
                path = os.path.join(sounds_dir, filename)
                if os.path.exists(path):
                    try:
                        snd = pygame.mixer.Sound(path)
                        snd.set_volume(SOUND_VOLUME)
                        self.sounds[name] = snd
                    except:
                        pass

        # 4. Load Pieces
        name_map = {'K': 'king', 'Q': 'queen', 'R': 'rook', 'B': 'bishop', 'N': 'knight', 'P': 'pawn'}
        if os.path.exists(pieces_dir):
            for color in ['w', 'b']:
                for p_type, p_name in name_map.items():
                    filename = f"{p_name}-{color}.png"
                    full_path = os.path.join(pieces_dir, filename)
                    if os.path.exists(full_path):
                        try:
                            key = f"{color}{p_type}"
                            self.original_images[key] = pygame.image.load(full_path).convert_alpha()
                        except:
                            pass

        # 5. Load Duck
        duck_paths = [os.path.join(assets_dir, "duck.png"), os.path.join(pieces_dir, "duck.png")]
        for path in duck_paths:
            if os.path.exists(path):
                try:
                    self.original_images['duck'] = pygame.image.load(path).convert_alpha()
                    break
                except:
                    pass

    def play_sound(self, name):
        """Plays a sound if it exists"""
        if name in self.sounds:
            self.sounds[name].play()

    def animate_move_visual(self, start, end, piece, is_duck=False):
        """
        Blocking animation loop.
        Moves a sprite from start to end over ANIMATION_SPEED ms.
        """
        if self.view_index != len(self.history) - 1:
            return

        x1, y1 = self.get_screen_pos(start[0], start[1])
        x2, y2 = self.get_screen_pos(end[0], end[1])

        key = 'duck' if is_duck else f"{piece.color}{piece.type}"
        img = self.scaled_images.get(key)

        if not img and not is_duck: return

        start_time = pygame.time.get_ticks()
        clock = pygame.time.Clock()

        while True:
            now = pygame.time.get_ticks()
            elapsed = now - start_time
            if elapsed >= ANIMATION_SPEED:
                break

            progress = elapsed / ANIMATION_SPEED
            progress = 1 - math.pow(1 - progress, 3)  # Cubic ease-out

            current_x = x1 + (x2 - x1) * progress
            current_y = y1 + (y2 - y1) * progress

            # Draw game with hidden start piece
            self.draw_game(hidden_square=start)

            # Draw Flying Piece
            if img:
                self.screen.blit(img, (current_x, current_y))

            pygame.display.flip()
            clock.tick(ANIMATION_FPS)

    def resize_layout(self, w, h):
        self.screen_w, self.screen_h = w, h
        bottom_hud_space = 90
        available_w = w - self.panel_width - self.side_margin * 2
        available_h = h - bottom_hud_space - self.side_margin
        self.sq_size = min(available_w - self.eval_bar_width - self.side_margin, available_h) // 8
        board_width = self.sq_size * 8
        total_center_width = self.eval_bar_width + self.side_margin + board_width
        start_x = self.side_margin + (available_w - total_center_width) // 2
        self.eval_bar_x = start_x
        self.board_x = self.eval_bar_x + self.eval_bar_width + self.side_margin
        self.board_y = self.side_margin + (available_h - (self.sq_size * 8)) // 2

        self.font_large = pygame.font.SysFont("Segoe UI Symbol", int(self.sq_size * 0.8), bold=True)
        self.font_ui = pygame.font.SysFont("Verdana", 14)
        self.font_history = pygame.font.SysFont("Consolas", 14)
        self.font_nav = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_menu_title = pygame.font.SysFont("Verdana", 60, bold=True)
        self.font_menu_sub = pygame.font.SysFont("Verdana", 16, bold=True)
        self.font_eval = pygame.font.SysFont("Arial", 16, bold=True)
        self.font_status = pygame.font.SysFont("Verdana", 18, bold=True)

        self.scaled_images = {}
        for key, img in self.original_images.items():
            sz = int(self.sq_size * 0.8) if key == 'duck' else self.sq_size
            self.scaled_images[key] = pygame.transform.smoothscale(img, (sz, sz))

        px, by = w - self.panel_width, h - 60
        bw, bh = self.panel_width // 4 - 8, 35
        self.nav_btns['start'] = pygame.Rect(px + 10, by, bw, bh)
        self.nav_btns['prev'] = pygame.Rect(px + 10 + bw + 5, by, bw, bh)
        self.nav_btns['next'] = pygame.Rect(px + 10 + (bw + 5) * 2, by, bw, bh)
        self.nav_btns['end'] = pygame.Rect(px + 10 + (bw + 5) * 3, by, bw, bh)

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
        if font is None: font = self.font_menu_sub
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

    def draw_eval_bar(self, current_board):
        if self.game_over:
            self.target_eval_score = 20 if self.winner == 'w' else -20
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
        if self.game_over and self.winner in ['w', 'b']:
            pygame.draw.rect(self.screen, EVAL_WHITE if self.winner == 'w' else EVAL_BLACK,
                             (bar_x, bar_y, bar_w, bar_h))

        score_txt = f"{abs(int(round(self.current_eval_score)))}"
        txt_surf = self.font_eval.render(score_txt, True, TEXT_COLOR if normalized > 0.95 else EVAL_WHITE)
        self.screen.blit(txt_surf, txt_surf.get_rect(center=(bar_x + bar_w // 2, bar_y + 15)))

    def draw_history_panel(self):
        # 1. Background & Title
        self.draw_glass_panel(pygame.Rect(self.screen_w - self.panel_width, 0, self.panel_width, self.screen_h))
        title = self.font_status.render("Move History", True, MENU_ACCENT)
        self.screen.blit(title, (self.screen_w - self.panel_width + 15, 15))

        # Turn Counter
        counter = self.font_ui.render(f"{self.view_index} / {len(self.history) - 1}", True, (150, 150, 150))
        self.screen.blit(counter, (self.screen_w - 90, 18))
        pygame.draw.line(self.screen, BTN_BORDER, (self.screen_w - self.panel_width + 10, 45), (self.screen_w - 10, 45))

        # 2. Setup Dimensions
        full_log = self.history[-1]['log']
        start_y = 55
        line_height = 24
        col_white_x = self.screen_w - self.panel_width + 10
        col_black_x = self.screen_w - self.panel_width + 155  # Adjusted spacing

        available_height = self.nav_btns['start'].top - start_y - 10
        max_rows = available_height // line_height
        total_rows = (len(full_log) + 1) // 2

        # Scroll Calculation
        current_ply_idx = self.view_index - 1
        current_row_idx = current_ply_idx // 2
        scroll_row = max(0, current_row_idx - (max_rows - 2)) if current_row_idx > max_rows - 2 else 0

        # 3. Draw Loop
        for row in range(scroll_row, min(total_rows, scroll_row + max_rows)):
            y_pos = start_y + (row - scroll_row) * line_height

            # --- White's Move (Left) ---
            w_idx = row * 2
            if w_idx < len(full_log):
                move_str = full_log[w_idx]
                is_active = (w_idx == current_ply_idx)

                if is_active:
                    bg_rect = pygame.Rect(col_white_x - 2, y_pos, 140, line_height)
                    pygame.draw.rect(self.screen, BTN_NORMAL, bg_rect, border_radius=4)

                color = MENU_ACCENT if is_active else (220, 220, 220)
                self.screen.blit(self.font_history.render(move_str, True, color), (col_white_x, y_pos + 4))

            # --- Black's Move (Right) ---
            b_idx = row * 2 + 1
            if b_idx < len(full_log):
                raw_str = full_log[b_idx]

                # --- FIX: ROBUST STRING CLEANING ---
                # Safely remove "1... " prefix by splitting on space and taking the last part(s)
                # If split fails, it defaults to printing the raw string.
                if "..." in raw_str:
                    parts = raw_str.split(' ', 1)
                    clean_str = parts[1] if len(parts) > 1 else raw_str
                else:
                    clean_str = raw_str
                # -----------------------------------

                is_active = (b_idx == current_ply_idx)
                if is_active:
                    bg_rect = pygame.Rect(col_black_x - 2, y_pos, 140, line_height)
                    pygame.draw.rect(self.screen, BTN_NORMAL, bg_rect, border_radius=4)

                color = MENU_ACCENT if is_active else (220, 220, 220)
                self.screen.blit(self.font_history.render(clean_str, True, color), (col_black_x, y_pos + 4))

        # 4. Draw Navigation Buttons
        mouse = pygame.mouse.get_pos()
        labels = [("<<", 'start'), ("<", 'prev'), (">", 'next'), (">>", 'end')]
        for lbl, key in labels:
            self.draw_styled_button(self.nav_btns[key], lbl, self.nav_btns[key].collidepoint(mouse), self.font_nav)    # --- NEW: GRAVEYARD METHOD ---
    def draw_game(self, hidden_square=None):
        self.draw_menu_background()

        is_live = (self.view_index == len(self.history) - 1)
        if is_live:
            board, d_pos, last_mv, prev_d = self.board, self.duck_pos, self.last_move_arrow, self.prev_duck_pos
        else:
            snap = self.history[self.view_index]
            board, d_pos, last_mv, prev_d = snap['board'], snap['duck_pos'], snap['last_move'], snap['prev_duck']

        # Dragging visual logic
        hide_pos = hidden_square
        if hasattr(self, 'dragging') and self.dragging and self.drag_start and is_live:
            hide_pos = self.drag_start

        # Board Border
        border_rect = pygame.Rect(self.board_x - 20, self.board_y - 20, self.sq_size * 8 + 40, self.sq_size * 8 + 40)
        pygame.draw.rect(self.screen, BTN_BORDER, border_rect, width=0, border_radius=4)
        pygame.draw.rect(self.screen, (20, 20, 20),
                         (self.board_x - 2, self.board_y - 2, self.sq_size * 8 + 4, self.sq_size * 8 + 4), width=2)

        # --- GRAVEYARD CALL REMOVED HERE ---

        font_coord = pygame.font.SysFont("Arial", 12, bold=True)

        for r in range(8):
            for c in range(8):
                x, y = self.get_screen_pos(r, c)
                color = WHITE_COLOR if (r + c) % 2 == 0 else BLACK_SQ_COLOR
                pygame.draw.rect(self.screen, color, (x, y, self.sq_size, self.sq_size))

                # Coords
                text_color = WHITE_COLOR if (r + c) % 2 != 0 else BLACK_SQ_COLOR
                is_bottom_row = (r == 7) if self.player_side == 'w' else (r == 0)
                if is_bottom_row:
                    file_char = "abcdefgh"[c]
                    txt = font_coord.render(file_char, True, text_color)
                    self.screen.blit(txt, (x + self.sq_size - 12, y + self.sq_size - 14))
                is_left_col = (c == 0) if self.player_side == 'w' else (c == 7)
                if is_left_col:
                    rank_char = "87654321"[r]
                    txt = font_coord.render(rank_char, True, text_color)
                    self.screen.blit(txt, (x + 3, y + 2))

                # Highlights
                if last_mv and ((r, c) == last_mv[0] or (r, c) == last_mv[1]):
                    s = pygame.Surface((self.sq_size, self.sq_size))
                    s.set_alpha(LAST_MOVE_COLOR[3])
                    s.fill(LAST_MOVE_COLOR[:3])
                    self.screen.blit(s, (x, y))
                if prev_d and (r, c) == prev_d:
                    s = pygame.Surface((self.sq_size, self.sq_size))
                    s.set_alpha(LAST_MOVE_COLOR[3])
                    s.fill(LAST_MOVE_COLOR[:3])
                    self.screen.blit(s, (x, y))

                if is_live and not self.promotion_pending:
                    if self.selected_square == (r, c): pygame.draw.rect(self.screen, HIGHLIGHT,
                                                                        (x, y, self.sq_size, self.sq_size))
                    if (r, c) in self.valid_moves:
                        s = pygame.Surface((self.sq_size, self.sq_size))
                        s.set_alpha(100)
                        s.fill((100, 255, 100))
                        self.screen.blit(s, (x, y))
                        pygame.draw.circle(self.screen, (50, 150, 50), (x + self.sq_size // 2, y + self.sq_size // 2),
                                           6)

                if hide_pos and (r, c) == hide_pos: continue
                if d_pos == (r, c): self.draw_duck(r, c)

                p = board[r][c]
                if p:
                    # Check Highlight
                    if p.type == 'K' and self.is_in_check(p.color, board):
                        s = pygame.Surface((self.sq_size, self.sq_size))
                        s.set_alpha(180)
                        s.fill((235, 60, 60))
                        self.screen.blit(s, (x, y))

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

        if hasattr(self, 'dragging') and self.dragging and self.drag_piece and is_live:
            mx, my = pygame.mouse.get_pos()
            draw_x, draw_y = mx - self.drag_offset[0], my - self.drag_offset[1]
            key = 'duck' if self.drag_piece == 'duck' else f"{self.drag_piece.color}{self.drag_piece.type}"
            if key in self.scaled_images: self.screen.blit(self.scaled_images[key], (draw_x, draw_y))

        self.draw_eval_bar(board)
        self.draw_history_panel()

        hud_w = self.screen_w - self.panel_width - 40
        hud_rect = pygame.Rect(20, self.screen_h - 70, hud_w, 60)
        self.draw_glass_panel(hud_rect)

        if self.game_over:
            status, status_col = f"WINNER: {'WHITE' if self.winner == 'w' else 'BLACK'}", MENU_ACCENT
        elif not is_live:
            status, status_col = "VIEWING HISTORY", (200, 200, 255)
        elif self.promotion_pending:
            status, status_col = "CHOOSE PROMOTION PIECE", MENU_ACCENT
        else:
            status, status_col = f"{'WHITE' if self.turn == 'w' else 'BLACK'} TO {'MOVE PIECE' if self.phase == 'move_piece' else 'PLACE DUCK'}", (
            220, 220, 220)

        self.screen.blit(self.font_status.render(status, True, status_col), (40, self.screen_h - 50))

        mouse = pygame.mouse.get_pos()
        btns = [("Menu", self.menu_btn_rect), ("Restart", self.restart_btn_rect)]
        if self.game_mode == 'pvp': btns.insert(1, ("Flip Board", self.flip_btn_rect))
        start_x = hud_rect.right - 20 - (len(btns) * 110)
        for i, (lbl, r) in enumerate(btns):
            r.width, r.height, r.x, r.centery = 100, 36, start_x + i * 110, hud_rect.centery
            self.draw_styled_button(r, lbl, r.collidepoint(mouse))

        if self.promotion_pending and is_live: self.draw_promotion_ui()
    def draw_menu(self):
        self.draw_menu_background()
        t_shadow = self.font_menu_title.render("DUCK CHESS", True, (0, 0, 0))
        self.screen.blit(t_shadow, t_shadow.get_rect(center=(self.screen_w // 2 + 3, self.screen_h * 0.2 + 3)))
        t_main = self.font_menu_title.render("DUCK CHESS", True, MENU_ACCENT)
        self.screen.blit(t_main, t_main.get_rect(center=(self.screen_w // 2, self.screen_h * 0.2)))
        ver = self.font_ui.render("Pro Edition v1.0", True, (150, 160, 170))
        self.screen.blit(ver, ver.get_rect(center=(self.screen_w // 2, self.screen_h * 0.26)))

        panel_rect = pygame.Rect((self.screen_w - 400) // 2, (self.screen_h - 320) // 2 + 40, 400, 320)
        self.draw_glass_panel(panel_rect)

        opts = [("Play as White", 'white_ai'), ("Play as Black", 'black_ai'), ("2 Player (PvP)", 'pvp')]
        mouse = pygame.mouse.get_pos()
        for i, (txt, mode) in enumerate(opts):
            r = pygame.Rect(0, 0, 300, 55)
            r.centerx, r.top = self.screen_w // 2, panel_rect.top + 50 + i * 80
            self.draw_styled_button(r, txt, r.collidepoint(mouse))
            if pygame.mouse.get_pressed()[0] and r.collidepoint(mouse):
                self.game_mode, self.player_side, self.state = mode, 'b' if mode == 'black_ai' else 'w', 'game'
                self.reset_game_state()
                pygame.time.wait(200)

    # ... Helper methods ...
    def get_screen_pos(self, r, c):
        dr, dc = (7 - r, 7 - c) if self.player_side == 'b' else (r, c)
        return self.board_x + dc * self.sq_size, self.board_y + dr * self.sq_size

    def get_board_pos(self, px, py):
        rx, ry = px - self.board_x, py - self.board_y
        if rx < 0 or ry < 0: return -1, -1
        c, r = rx // self.sq_size, ry // self.sq_size
        if c >= 8 or r >= 8: return -1, -1
        return (7 - r, 7 - c) if self.player_side == 'b' else (r, c)

    def get_promotion_rects(self):
        if not self.promotion_coords: return []
        r, c = self.promotion_coords
        bx, by = self.get_screen_pos(r, c)

        # 1. Force the order: Queen (Top), Rook, Bishop, Knight (Bottom)
        opts = [QUEEN, ROOK, BISHOP, KNIGHT]

        # 2. Center the menu vertically over the pawn
        menu_h = self.sq_size * len(opts)
        start_y = by + (self.sq_size - menu_h) // 2

        # 3. Clamp to board edges (so it doesn't fly off screen)
        board_top = self.board_y
        board_bottom = self.board_y + self.sq_size * 8

        if start_y < board_top:
            start_y = board_top
        elif start_y + menu_h > board_bottom:
            start_y = board_bottom - menu_h

        # 4. Generate Rects
        rects = []
        for i, p in enumerate(opts):
            rect = pygame.Rect(bx, start_y + i * self.sq_size, self.sq_size, self.sq_size)
            rects.append((rect, p))

        return rects
    def draw_promotion_ui(self):
        rects = self.get_promotion_rects()
        if not rects: return
        container = rects[0][0].unionall([r[0] for r in rects])
        pygame.draw.rect(self.screen, EVAL_WHITE, container)
        pygame.draw.rect(self.screen, BTN_BORDER, container, width=2)
        m = pygame.mouse.get_pos()
        for r, p in rects:
            if r.collidepoint(m): pygame.draw.rect(self.screen, HIGHLIGHT, r)
            k = f"{self.turn}{p}"
            if k in self.scaled_images: self.screen.blit(self.scaled_images[k], r)

    def draw_duck(self, r, c):
        x, y = self.get_screen_pos(r, c)
        if 'duck' in self.scaled_images:
            img = self.scaled_images['duck']
            self.screen.blit(img,
                             (x + (self.sq_size - img.get_width()) // 2, y + (self.sq_size - img.get_height()) // 2))
        else:
            pygame.draw.circle(self.screen, (255, 220, 0), (x + self.sq_size // 2, y + self.sq_size // 2),
                               self.sq_size // 3)