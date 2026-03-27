import pygame
from DuckChess_Game.UI.settings import *
from DuckChess_Game.Logic.constants import *

class BaseRenderingMixin:
	"""Core layout math, window resizing, and common drawing helpers."""

	def resize_layout(self, w, h):
		"""Recalculates board and UI element positions based on new window dimensions [cite: 67-68]."""
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
		for key, img in getattr(self, 'original_images', {}).items():
			sz = int(self.sq_size * 0.8) if key == 'duck' else self.sq_size
			self.scaled_images[key] = pygame.transform.smoothscale(img, (sz, sz))

		px, by = w - self.panel_width, h - 60
		bw, bh = self.panel_width // 4 - 8, 35

		self.nav_btns['start'] = pygame.Rect(px + 10, by, bw, bh)
		self.nav_btns['prev'] = pygame.Rect(px + 10 + bw + 5, by, bw, bh)
		self.nav_btns['next'] = pygame.Rect(px + 10 + (bw + 5) * 2, by, bw, bh)
		self.nav_btns['end'] = pygame.Rect(px + 10 + (bw + 5) * 3, by, bw, bh)

	def get_screen_pos(self, r, c):
		"""Converts board indices to screen pixel coordinates [cite: 68-69]."""
		dr, dc = (7 - r, 7 - c) if self.player_side == 'b' else (r, c)
		return self.board_x + dc * self.sq_size, self.board_y + dr * self.sq_size

	def get_board_pos(self, px, py):
		"""Converts screen pixel coordinates to board indices[cite: 69]."""
		rx, ry = px - self.board_x, py - self.board_y
		if rx < 0 or ry < 0: return -1, -1
		c, r = rx // self.sq_size, ry // self.sq_size
		if c >= 8 or r >= 8: return -1, -1
		return (7 - r, 7 - c) if self.player_side == 'b' else (r, c)

	def _draw_piece_sprite(self, p, x, y):
		"""Draws the piece image or falls back to Unicode characters ."""
		key = f"{p.color}{p.type}"
		if key in self.scaled_images:
			self.screen.blit(self.scaled_images[key], (x, y))
		else:
			txt = UNICODE_PIECES[p.color][p.type]
			tc = (0, 0, 0) if p.color == 'b' else (255, 255, 255)
			sf = self.font_large.render(txt, True, tc)
			rc = sf.get_rect(center=(x + self.sq_size // 2, y + self.sq_size // 2))
			if p.color == 'w':
				ol = self.font_large.render(txt, True, (0, 0, 0))
				self.screen.blit(ol, ol.get_rect(center=(rc.centerx + 2, rc.centery + 2)))
			self.screen.blit(sf, rc)

	def _draw_highlight_square(self, r, c, rgba_color):
		"""Draws a semi-transparent colored overlay on a specific square[cite: 70]."""
		x, y = self.get_screen_pos(r, c)
		s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
		s.fill(rgba_color)
		self.screen.blit(s, (x, y))