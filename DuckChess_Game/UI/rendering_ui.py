import pygame
import random
import math
from DuckChess_Game.UI.settings import *

class UIRenderingMixin:
	"""Handles the rendering of Main Menu, in-game HUD, and navigation log."""

	def draw_menu_background(self):
		"""Draws a deep ocean gradient background and a dynamic particle field."""
		self.screen.fill(COLOR_BG)
		max_radius = int(math.sqrt(self.screen_w ** 2 + self.screen_h ** 2))
		center_col = COLOR_BG
		edge_col = (20, 30, 45, 10)
		for r in range(max_radius, 0, -max_radius // 6):
			progress = (max_radius - r) / max_radius
			col = [int(center_col[i] * (1 - progress) + edge_col[i] * progress) for i in range(3)]
			pygame.draw.circle(self.screen, col, (self.screen_w // 2, self.screen_h // 2), r)

		if not hasattr(self, 'particles'):
			self.particles = []
			for _ in range(70):
				self.particles.append({'x': random.uniform(0, self.screen_w), 'y': random.uniform(0, self.screen_h), 'size': random.uniform(1.0, 3.5), 'speed': random.uniform(0.1, 0.4)})
		
		particle_surf = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
		time_ms = pygame.time.get_ticks()
		for p in self.particles:
			p['y'] -= p['speed']
			p['x'] += 0.2 * math.sin(time_ms * 0.001 + p['y'] * 0.01)
			if p['y'] < -10: p['y'] = self.screen_h + 10
			if p['x'] < -10: p['x'] = self.screen_w + 10
			if p['x'] > self.screen_w + 10: p['x'] = -10
			alpha = 100 + 100 * math.sin(time_ms * 0.002 + p['y'] * 0.05)
			pygame.draw.circle(particle_surf, (0, 255, 255, int(alpha * 0.15)), (int(p['x']), int(p['y'])), int(p['size'] * 2))
			pygame.draw.circle(particle_surf, (220, 240, 255, int(alpha * 0.7)), (int(p['x']), int(p['y'])), int(p['size']))
		self.screen.blit(particle_surf, (0, 0))

	def draw_menu(self):
		"""Renders the modernized, atmospheric Main Menu."""
		self.draw_menu_background()
		mouse_pos = pygame.mouse.get_pos()
		center_x = self.screen_w // 2
		start_y = max(50, self.screen_h // 2 - 280)
		logo_rect = pygame.Rect(center_x - 60, start_y, 120, 120)
		pulse = 180 + 75 * math.sin(pygame.time.get_ticks() * 0.005)
		s_duck = pygame.Surface((120, 120), pygame.SRCALPHA)
		pygame.draw.circle(s_duck, (COLOR_DUCK_ACCENT[0], COLOR_DUCK_ACCENT[1], COLOR_DUCK_ACCENT[2], int(pulse * 0.2)), (60, 60), 60)
		pygame.draw.circle(s_duck, (COLOR_DUCK_ACCENT[0], COLOR_DUCK_ACCENT[1], COLOR_DUCK_ACCENT[2], int(pulse * 0.5)), (60, 60), 45, width=15)
		pygame.draw.circle(s_duck, COLOR_DUCK_ACCENT, (60, 60), 45)
		pygame.draw.circle(s_duck, (10, 10, 10), (45, 45), 5)
		self.screen.blit(s_duck, logo_rect.topleft)

		font_title = pygame.font.SysFont("Arial", 72, bold=True)
		font_subtitle = pygame.font.SysFont("Arial", 20, bold=True)
		duck_center = (center_x - 110, start_y + 160)
		chess_center = (center_x + 90, start_y + 160)
		self._draw_text_with_glow(self.screen, "DUCK", font_title, duck_center, COLOR_DUCK_ACCENT, COLOR_DUCK_VALID[:3])
		self._draw_text_with_glow(self.screen, "CHESS", font_title, chess_center, COLOR_HIGHLIGHT[:3], BTN_BORDER[:3])
		self.screen.blit(font_subtitle.render("Strategic Anarchy", True, COLOR_TEXT), (center_x - 80, start_y + 200))

		if not hasattr(self, 'menu_rects'):
			self.menu_rects = {}
			self.btn_order = ['white', 'black', 'pvp', 'edit', 'replay', 'quit']
			self.btn_labels = {'white': 'Play White', 'black': 'Play Black', 'pvp': '2 Player', 'edit': 'Editor', 'replay': 'Load Replay', 'quit': 'Exit'}

		btn_width, btn_height, btn_spacing = 300, 45, 15
		for i, key in enumerate(self.btn_order):
			r = pygame.Rect(center_x - btn_width // 2, start_y + 250 + i * (btn_height + btn_spacing), btn_width, btn_height)
			self.menu_rects[key] = r
			self.draw_styled_menu_button(r, self.btn_labels[key], r.collidepoint(mouse_pos))

		footer_txt = self.font_ui.render("v1.5: Deep Ocean & Neon Update | 2026", True, (60, 80, 100))
		self.screen.blit(footer_txt, footer_txt.get_rect(center=(center_x, self.screen_h - 20)))

	def draw_history_panel_2_column(self):
		"""Draws move history and navigation arrows in the side panel."""
		board_h = self.sq_size * 8
		panel_rect = pygame.Rect(self.screen_w - self.panel_width + 10, self.board_y, self.panel_width - 20, board_h)
		self.draw_glass_panel(panel_rect, border_radius=10)
		
		font_headers = pygame.font.SysFont("Arial", 16, bold=True)
		self.screen.blit(font_headers.render("STRATEGIC ANARCHY LOG", True, COLOR_ACCENT_WHITE), (panel_rect.x + 15, panel_rect.y + 15))
		
		grouped_moves = []
		turn_data = None
		for move_str in self.move_log:
			if "..." in move_str:
				parts = move_str.split("... ")
				b_move = parts[1] if len(parts) > 1 else move_str
				if turn_data: turn_data = (turn_data[0], turn_data[1], b_move)
				else: turn_data = ("", "---", b_move)
				grouped_moves.append(turn_data); turn_data = None
			else:
				parts = move_str.split(". ")
				t_num = parts[0] + "." if len(parts) > 1 else ""
				w_move = parts[1] if len(parts) > 1 else move_str
				turn_data = (t_num, w_move, "")
		if turn_data: grouped_moves.append(turn_data)

		pygame.draw.line(self.screen, (60, 80, 100), (panel_rect.x + 10, panel_rect.y + 40), (panel_rect.right - 10, panel_rect.y + 40))
		
		font_list = pygame.font.SysFont("Consolas", 14)
		start_y = panel_rect.y + 50
		line_h = 20
		max_lines = (panel_rect.height - 110) // line_h
		start_idx = max(0, len(grouped_moves) - max_lines)
		
		for i, (tnum, wmove, bmove) in enumerate(grouped_moves[start_idx:]):
			y = start_y + i * line_h
			col = COLOR_HIGHLIGHT[:3] if (i + start_idx == len(grouped_moves)-1) else COLOR_TEXT
			self.screen.blit(font_list.render(tnum, True, (100, 120, 140)), (panel_rect.x + 15, y))
			self.screen.blit(font_list.render(wmove, True, col), (panel_rect.x + 55, y))
			self.screen.blit(font_list.render(bmove, True, col), (panel_rect.x + 160, y))

		self._draw_log_navigation(panel_rect)

	def _draw_log_navigation(self, panel_rect):
		"""Renders the navigation buttons at the bottom of the log panel."""
		mouse = pygame.mouse.get_pos()
		btn_w = (panel_rect.width - 40) // 4
		labels = [("|<", 'start'), ("<", 'prev'), (">", 'next'), (">|", 'end')]
		for i, (lbl, key) in enumerate(labels):
			r = pygame.Rect(panel_rect.x + 10 + i * (btn_w + 5), panel_rect.bottom - 45, btn_w, 35)
			self.nav_btns[key] = r
			is_hover = r.collidepoint(mouse)
			pygame.draw.rect(self.screen, COLOR_HIGHLIGHT[:3] if is_hover else (60, 80, 100), r, width=1, border_radius=5)
			txt = self.font_nav.render(lbl, True, COLOR_TEXT)
			self.screen.blit(txt, txt.get_rect(center=r.center))

	def draw_in_game_hud(self):
		"""Draws a simplified, cleaner HUD with more vertical space (80px)."""
		is_live = (self.view_index == len(self.history) - 1)
		board_width = self.sq_size * 8
		hud_height = 80
		hud_start_y = self.board_y + board_width + self.side_margin 
		hud_rect = pygame.Rect(self.board_x - 10, hud_start_y, board_width + 20, hud_height)
		self.draw_glass_panel(hud_rect, border_radius=10)

		status_txt = ""
		status_col = COLOR_TEXT

		if self.state == 'edit':
			valid = self.validate_editor_board()
			status_txt = "READY" if valid else "INVALID BOARD (KINGS?)"
			status_col = COLOR_HIGHLIGHT[:3] if valid else COLOR_CAPTURE_MOVE[:3]
		elif self.game_over:
			status_txt = f"WINNER: {self.winner.upper()}" if self.winner != 'draw' else "DRAW"
			status_col = COLOR_CAPTURE_MOVE[:3]
		elif not is_live:
			status_txt = f"VIEWING: {self.view_index + 1}/{len(self.history)}"
			status_col = COLOR_VALID_MOVE
		elif self.promotion_pending:
			status_txt = "PROMOTION"
			status_col = COLOR_DUCK_VALID
		else:
			t_col = 'WHITE' if self.turn == 'w' else 'BLACK'
			ph = 'MOVE' if self.phase == 'move_piece' else 'DUCK'
			status_txt = f"{t_col} TURN: {ph}"
			status_col = COLOR_TEXT

		font_status_hud = pygame.font.SysFont("Arial", 18, bold=True)
		status_surf = font_status_hud.render(status_txt, True, status_col)
		self.screen.blit(status_surf, (hud_rect.x + 20, hud_rect.centery - status_surf.get_height() // 2))

		mouse = pygame.mouse.get_pos()
		if self.state == 'edit':
			btns = [("Menu", self.editor_menu_btn), ("Clear", self.editor_clear_btn)]
			if self.validate_editor_board(): btns.append(("Play", self.editor_play_btn))
			turn_lbl = f"START: {'W' if self.turn == 'w' else 'B'}"
			btns.insert(1, (turn_lbl, self.editor_turn_btn))
		else:
			btns = [("Menu", self.menu_btn_rect), ("Eval" if not self.show_eval else "No Eval", self.eval_btn_rect), ("Restart", self.restart_btn_rect)]
			if self.game_mode == 'pvp': btns.insert(2, ("Flip", self.flip_btn_rect))

		start_x = hud_rect.right - 20 - (len(btns) * 110)
		for i, (lbl, rect_obj) in enumerate(btns):
			rect_obj.update(start_x + i * 110, hud_rect.centery - 22, 100, 45) 
			self.draw_styled_hud_button(rect_obj, lbl, rect_obj.collidepoint(mouse))

	def draw_glass_panel(self, rect, border_radius=0):
		"""Helper for translucent frosted glass effect."""
		s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
		pygame.draw.rect(s, (20, 30, 45, 200), (0, 0, rect.width, rect.height), border_radius=border_radius)
		self.screen.blit(s, rect.topleft)
		pygame.draw.rect(self.screen, BTN_BORDER, rect, width=2, border_radius=border_radius)

	def draw_styled_hud_button(self, rect, label, is_hover):
		"""Draws a themed button for HUD interaction."""
		s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
		if is_hover:
			pygame.draw.rect(s, (0, 255, 255, 60), (0, 0, rect.width, rect.height), border_radius=5)
			border_col, text_col = COLOR_HIGHLIGHT[:3], (255, 255, 255)
		else:
			pygame.draw.rect(s, (30, 45, 60, 200), (0, 0, rect.width, rect.height), border_radius=5)
			border_col, text_col = (60, 80, 100), COLOR_TEXT
		self.screen.blit(s, rect.topleft)
		pygame.draw.rect(self.screen, border_col, rect, width=1, border_radius=5)
		txt_surf = pygame.font.SysFont("Arial", 14, bold=True).render(label, True, text_col)
		self.screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

	def _draw_text_with_glow(self, surf, text, font, center_pos, core_col, glow_col):
		"""Helper to render glowing text effect."""
		t_surf = font.render(text, True, glow_col)
		t_rect = t_surf.get_rect(center=center_pos)
		pulse = 120 + 80 * math.sin(pygame.time.get_ticks() * 0.005)
		t_surf.set_alpha(int(pulse * 0.2))
		surf.blit(t_surf, (t_rect.x - 4, t_rect.y - 4))
		t_surf.set_alpha(int(pulse * 0.5))
		surf.blit(t_surf, (t_rect.x - 2, t_rect.y - 2))
		surf.blit(font.render(text, True, core_col), t_rect)

	def draw_styled_menu_button(self, rect, label, is_hover):
		"""Draws high-quality menu buttons with glows."""
		s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
		if is_hover:
			pulse = 60 + 20 * math.sin(pygame.time.get_ticks() * 0.005)
			pygame.draw.rect(s, (40, 60, 80, int(pulse)), (0, 0, rect.width, rect.height), border_radius=8)
			border_col, text_col = COLOR_HIGHLIGHT[:3], (255, 255, 255)
			glow_s = pygame.Surface((rect.width + 30, rect.height + 30), pygame.SRCALPHA)
			pygame.draw.rect(glow_s, (0, 255, 255, 25), (15, 15, rect.width, rect.height), border_radius=12)
			pygame.draw.rect(glow_s, (0, 255, 255, 60), (0, 0, rect.width + 30, rect.height + 30), width=15, border_radius=15)
			self.screen.blit(glow_s, (rect.x - 15, rect.y - 15))
		else:
			pygame.draw.rect(s, (30, 45, 60, 100), (0, 0, rect.width, rect.height), border_radius=8)
			border_col, text_col = (60, 80, 100), COLOR_TEXT
		self.screen.blit(s, rect.topleft)
		pygame.draw.rect(self.screen, border_col, rect, width=2, border_radius=8)
		txt_surf = pygame.font.SysFont("Arial", 18, bold=True).render(label, True, text_col)
		self.screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

	def draw_eval_bar(self, board):
		"""Draws the vertical material evaluation bar."""
		bar_rect = pygame.Rect(self.side_margin + 5, self.board_y, self.eval_bar_width, self.sq_size * 8)
		pygame.draw.rect(self.screen, EVAL_BLACK, bar_rect, border_radius=5)
		score = self.calculate_material_score(board)
		vis_score = max(-15, min(15, score))
		fill_pct = (vis_score + 15) / 30.0
		white_h = int(bar_rect.height * fill_pct)
		if white_h > 0:
			white_rect = pygame.Rect(bar_rect.x, bar_rect.bottom - white_h, bar_rect.width, white_h)
			pygame.draw.rect(self.screen, EVAL_WHITE, white_rect, border_bottom_left_radius=5, border_bottom_right_radius=5)
			if white_h >= bar_rect.height: pygame.draw.rect(self.screen, EVAL_WHITE, white_rect, border_radius=5)
		pygame.draw.rect(self.screen, BTN_BORDER, bar_rect, width=2, border_radius=5)

	def draw_promotion_ui(self):
		"""Draws selection UI for pawn promotion."""
		overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
		overlay.fill((0, 0, 0, 150))
		self.screen.blit(overlay, (0, 0))
		spacing = self.sq_size + 20
		panel_w, panel_h = spacing * 4 + 20, self.sq_size + 40
		rect = pygame.Rect((self.screen_w - panel_w)//2, (self.screen_h - panel_h)//2, panel_w, panel_h)
		self.draw_glass_panel(rect, border_radius=10)
		for r, p_type in self.get_promotion_rects():
			if r.collidepoint(pygame.mouse.get_pos()): pygame.draw.rect(self.screen, COLOR_HIGHLIGHT, r, border_radius=5)
			key = f"{self.turn}{p_type}"
			if key in self.scaled_images: self.screen.blit(self.scaled_images[key], (r.x, r.y))

	def get_promotion_rects(self):
		"""Calculates rects for promotion selection."""
		pieces, rects = [QUEEN, ROOK, BISHOP, KNIGHT], []
		spacing = self.sq_size + 20
		panel_w = spacing * 4 + 20
		start_x, start_y = (self.screen_w - panel_w)//2 + 20, (self.screen_h - (self.sq_size + 40))//2 + 20
		for i, p_type in enumerate(pieces):
			r = pygame.Rect(start_x + i * spacing, start_y, self.sq_size, self.sq_size)
			rects.append((r, p_type))
		return rects