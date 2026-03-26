import pygame
from DuckChess_Game.UI.settings import *

class HUDRenderingMixin:
	"""Handles in-game UI overlays: eval bar, history panel, and control buttons."""

	def draw_eval_bar(self, current_board):
		"""Draws the dynamic material evaluation bar [cite: 188-192]."""
		if self.game_over: self.target_eval_score = 0 if self.winner == 'draw' else (20 if self.winner == 'w' else -20)
		else: self.target_eval_score = self.calculate_material_score(current_board)

		diff = self.target_eval_score - self.current_eval_score
		self.current_eval_score = self.target_eval_score if abs(diff) < 0.05 else self.current_eval_score + diff * 0.1

		max_adv = 20
		normalized = (max(-max_adv, min(max_adv, self.current_eval_score)) + max_adv) / (2 * max_adv)
		bar_h, bar_y, bar_x, bar_w = self.sq_size * 8, self.board_y, self.eval_bar_x, self.eval_bar_width

		pygame.draw.rect(self.screen, BTN_BORDER, (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=4)
		mid_y = bar_y + bar_h * (1 - normalized)
		pygame.draw.rect(self.screen, EVAL_BLACK, (bar_x, bar_y, bar_w, mid_y - bar_y))
		pygame.draw.rect(self.screen, EVAL_WHITE, (bar_x, mid_y, bar_w, bar_y + bar_h - mid_y))

		if self.game_over:
			col = EVAL_WHITE if self.winner == 'w' else (EVAL_BLACK if self.winner == 'b' else (150, 150, 150))
			pygame.draw.rect(self.screen, col, (bar_x, bar_y, bar_w, bar_h))

		txt = self.font_eval.render(f"{abs(int(round(self.current_eval_score)))}", True, TEXT_COLOR if normalized > 0.95 else EVAL_WHITE)
		self.screen.blit(txt, txt.get_rect(center=(bar_x + bar_w // 2, bar_y + 15)))

	def draw_history_panel(self):
		"""Renders the scrolling move history panel on the right [cite: 192-200]."""
		self.draw_glass_panel(pygame.Rect(self.screen_w - self.panel_width, 0, self.panel_width, self.screen_h))
		self.screen.blit(self.font_status.render("Move History", True, MENU_ACCENT), (self.screen_w - self.panel_width + 15, 15))
		
		counter = self.font_ui.render(f"{self.view_index} / {max(0, len(self.history) - 1)}", True, (150, 150, 150))
		self.screen.blit(counter, (self.screen_w - 90, 18))
		pygame.draw.line(self.screen, BTN_BORDER, (self.screen_w - self.panel_width + 10, 45), (self.screen_w - 10, 45))

		if not self.history: return
		full_log = self.history[-1]['log']
		max_rows = (self.nav_btns['start'].top - 65) // 24
		scroll = max(0, ((self.view_index - 1) // 2) - (max_rows - 2)) if ((self.view_index - 1) // 2) > max_rows - 2 else 0

		for row in range(scroll, min((len(full_log) + 1) // 2, scroll + max_rows)):
			y = 55 + (row - scroll) * 24
			for i, offset in enumerate([(0, 10), (1, 155)]):
				idx = row * 2 + i
				if idx < len(full_log):
					active = (idx == self.view_index - 1)
					if active: pygame.draw.rect(self.screen, BTN_NORMAL, pygame.Rect(self.screen_w - self.panel_width + offset[1] - 12, y, 140, 24), border_radius=4)
					txt = full_log[idx].split(' ', 1)[1] if "..." in full_log[idx] and i == 1 else full_log[idx]
					self.screen.blit(self.font_history.render(txt, True, MENU_ACCENT if active else (220, 220, 220)), (self.screen_w - self.panel_width + offset[1], y + 4))

		mouse = pygame.mouse.get_pos()
		for lbl, k in [("<<", 'start'), ("<", 'prev'), (">", 'next'), (">>", 'end')]:
			self.draw_styled_button(self.nav_btns[k], lbl, self.nav_btns[k].collidepoint(mouse), self.font_nav)

	def draw_in_game_hud(self):
		"""Draws the bottom control bar during active gameplay [cite: 169-173]."""
		hud = pygame.Rect(20, self.screen_h - 70, self.screen_w - self.panel_width - 40, 60)
		self.draw_glass_panel(hud)

		is_live = (self.view_index == len(self.history) - 1)
		if self.game_over:
			status, col = ("GAME OVER: DRAW", (200, 200, 200)) if self.winner == 'draw' else (f"WINNER: {'WHITE' if self.winner == 'w' else 'BLACK'}", MENU_ACCENT)
		elif not is_live: status, col = "VIEWING HISTORY", (200, 200, 255)
		elif getattr(self, 'promotion_pending', False): status, col = "CHOOSE PROMOTION PIECE", MENU_ACCENT
		else: status, col = f"{'WHITE' if self.turn == 'w' else 'BLACK'} TO {'MOVE PIECE' if self.phase == 'move_piece' else 'PLACE DUCK'}", (220, 220, 220)

		self.screen.blit(self.font_status.render(status, True, col), (40, self.screen_h - 50))

		mouse = pygame.mouse.get_pos()
		btns = [("Menu", self.menu_btn_rect), ("Hide Eval" if getattr(self, 'show_eval', True) else "Show Eval", self.eval_btn_rect), ("Restart", self.restart_btn_rect)]
		if getattr(self, 'game_mode', '') == 'pvp': btns.insert(2, ("Flip Board", self.flip_btn_rect))

		for i, (lbl, r) in enumerate(btns):
			r.update(hud.right - 20 - (len(btns) * 110) + i * 110, hud.centery - 18, 100, 36)
			self.draw_styled_button(r, lbl, r.collidepoint(mouse))