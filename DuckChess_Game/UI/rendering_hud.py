import pygame
from DuckChess_Game.UI.settings import *

class HUDRenderingMixin:
	"""Handles in-game UI overlays with glossy, colorful jewel buttons without yellow borders."""

	def draw_eval_bar(self, current_board):
		"""Draws the dynamic material evaluation bar."""
		if getattr(self, 'game_over', False): 
			self.target_eval_score = 0 if self.winner == 'draw' else (20 if self.winner == 'w' else -20)
		else: 
			self.target_eval_score = self.calculate_material_score(current_board)

		diff = self.target_eval_score - getattr(self, 'current_eval_score', 0.0)
		self.current_eval_score = getattr(self, 'current_eval_score', 0.0) + diff * 0.1

		max_adv = 20
		normalized = (max(-max_adv, min(max_adv, self.current_eval_score)) + max_adv) / (2 * max_adv)
		bar_h, bar_y, bar_x, bar_w = self.sq_size * 8, self.board_y, self.eval_bar_x, self.eval_bar_width

		pygame.draw.rect(self.screen, BTN_BORDER, (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=4)
		mid_y = bar_y + bar_h * (1 - normalized)
		pygame.draw.rect(self.screen, EVAL_BLACK, (bar_x, bar_y, bar_w, mid_y - bar_y))
		pygame.draw.rect(self.screen, EVAL_WHITE, (bar_x, mid_y, bar_w, bar_y + bar_h - mid_y))

		txt = FONT_EVAL.render(f"{abs(int(round(self.current_eval_score)))}", True, TEXT_COLOR if normalized > 0.95 else EVAL_WHITE)
		self.screen.blit(txt, txt.get_rect(center=(bar_x + bar_w // 2, bar_y + 15)))

	def draw_history_panel(self):
		"""Renders the scrollable move history panel with text caching for maximum performance."""
		panel_rect = pygame.Rect(self.screen_w - PANEL_WIDTH, 0, PANEL_WIDTH, self.screen_h)
		self.draw_glass_panel(panel_rect)
		self.screen.blit(FONT_STATUS.render("Move History", True, TEXT_COLOR), (self.screen_w - PANEL_WIDTH + 15, 15))
		
		counter = FONT_UI.render(f"{self.view_index} / {max(0, len(self.history) - 1)}", True, (150, 150, 150))
		self.screen.blit(counter, (self.screen_w - 90, 18))
		pygame.draw.line(self.screen, BTN_BORDER, (self.screen_w - PANEL_WIDTH + 10, 45), (self.screen_w - 10, 45))

		if not self.history: return
		full_log = self.history[-1]['log']
		row_height = 24
		max_rows = (self.nav_btns['start'].top - 65) // row_height
		total_rows = (len(full_log) + 1) // 2
		
		if not hasattr(self, 'history_scroll_offset'): self.history_scroll_offset = 0
		if not getattr(self, 'is_user_scrolling', False):
			self.history_scroll_offset = max(0, ((self.view_index - 1) // 2) - (max_rows - 2))

		scroll = max(0, min(self.history_scroll_offset, max(0, total_rows - max_rows)))
		self.move_click_rects = {} 
		mouse = pygame.mouse.get_pos()

		if not hasattr(self, '_history_text_cache'): self._history_text_cache = {}

		for row in range(scroll, min(total_rows, scroll + max_rows + 1)):
			y = 55 + (row - scroll) * row_height
			if y > self.nav_btns['start'].top - 15: continue
			for i, offset in enumerate([(0, 10), (1, 155)]):
				idx = row * 2 + i
				if idx < len(full_log):
					active = (idx == self.view_index - 1)
					rect = pygame.Rect(self.screen_w - PANEL_WIDTH + offset[1] - 8, y, 130, row_height)
					self.move_click_rects[idx] = rect
					
					if active: pygame.draw.rect(self.screen, (65, 75, 85), rect, border_radius=4)
					elif rect.collidepoint(mouse) and panel_rect.collidepoint(mouse):
						pygame.draw.rect(self.screen, (50, 58, 68), rect, border_radius=4)
					
					txt = full_log[idx].split(' ', 1)[1] if "..." in full_log[idx] and i == 1 else full_log[idx]
					color = (255, 255, 255) if active else (180, 180, 180)
					
					cache_key = (txt, color)
					if cache_key not in self._history_text_cache:
						self._history_text_cache[cache_key] = FONT_HISTORY.render(txt, True, color)
					
					self.screen.blit(self._history_text_cache[cache_key], (rect.x + 8, y + 4))

		for lbl, k in [("<<", 'start'), ("<", 'prev'), (">", 'next'), (">>", 'end')]:
			self.draw_hud_button(self.nav_btns[k], lbl, self.nav_btns[k].collidepoint(mouse))

	def draw_in_game_hud(self):
		"""Draws the bottom control bar with vibrant jewel-style buttons."""
		hud = pygame.Rect(20, self.screen_h - 70, self.screen_w - PANEL_WIDTH - 40, 60)
		self.draw_glass_panel(hud)

		is_live = (self.view_index == len(self.history) - 1)
		if getattr(self, 'game_over', False):
			status, col = ("GAME OVER", TEXT_COLOR)
		elif not is_live: status, col = "VIEWING HISTORY", (200, 200, 255)
		else: status, col = f"{'WHITE' if self.turn == 'w' else 'BLACK'} TO {self.phase.replace('_', ' ').upper()}", (220, 220, 220)

		self.screen.blit(FONT_STATUS.render(status, True, col), (40, self.screen_h - 50))

		mouse = pygame.mouse.get_pos()
		eval_txt = "Hide Eval" if getattr(self, 'show_eval', True) else "Show Eval"
		btns = [("Menu", self.menu_btn_rect), (eval_txt, self.eval_btn_rect), ("Reset", self.restart_btn_rect)]
		if getattr(self, 'game_mode', '') == 'pvp': btns.insert(1, ("Flip", self.flip_btn_rect))

		btn_w, btn_h, spacing = 95, 36, 12
		start_x = hud.right - (btn_w + spacing) * len(btns) - 15
		for i, (lbl, r) in enumerate(btns):
			r.update(start_x + i * (btn_w + spacing), hud.centery - btn_h // 2, btn_w, btn_h)
			self.draw_hud_button(r, lbl, r.collidepoint(mouse))

	def draw_hud_button(self, rect, text, hover):
		"""Renders a glossy, colorful 'jewel-like' button without the yellow casing."""
		radius = 14
		
		# 1. Drop Shadow
		shadow_rect = rect.copy()
		shadow_rect.y += 3
		pygame.draw.rect(self.screen, (0, 0, 0, 120), shadow_rect, border_radius=radius)
		
		# 2. Casing (Outer) - Uses slate/dark border instead of gold
		casing_color = (100, 110, 130) if hover else (60, 65, 75)
		pygame.draw.rect(self.screen, casing_color, rect, border_radius=radius)
		
		# 3. Colored Inner Pill (The "Jewel")
		inner_rect = rect.inflate(-2, -2)
		if hover:
			inner_rect.y += 1
		
		core_color = BTN_HOVER if hover else BTN_NORMAL 
		pygame.draw.rect(self.screen, core_color, inner_rect, border_radius=radius-2)
		
		# 4. Glossy Highlight (Top half)
		highlight_rect = pygame.Rect(inner_rect.x, inner_rect.y, inner_rect.width, inner_rect.height // 2)
		highlight_surf = pygame.Surface((highlight_rect.width, highlight_rect.height), pygame.SRCALPHA)
		pygame.draw.rect(highlight_surf, (255, 255, 255, 25), highlight_surf.get_rect(), border_radius=radius-2)
		self.screen.blit(highlight_surf, highlight_rect.topleft)

		# 5. Crisp Text
		txt_surf = FONT_UI.render(text, True, BTN_TEXT)
		self.screen.blit(txt_surf, txt_surf.get_rect(center=inner_rect.center))

	def draw_glass_panel(self, rect):
		"""Draws a refined frosted glass panel with a clean border."""
		s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
		s.fill(PANEL_BG)
		self.screen.blit(s, rect.topleft)
		pygame.draw.rect(self.screen, BTN_BORDER, rect, width=1, border_radius=15)