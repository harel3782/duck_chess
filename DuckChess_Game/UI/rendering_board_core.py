import pygame
from DuckChess_Game.UI.settings import *

class BoardCoreRenderingMixin:
	"""Handles the physical 8x8 grid with a high-end walnut frame look."""

	def _draw_base_board(self):
		"""Draws the walnut and maple inlay squares and coordinate notation."""
		# Draw a thick wooden frame around the board
		frame_rect = pygame.Rect(self.board_x - 15, self.board_y - 15, self.sq_size * 8 + 30, self.sq_size * 8 + 30)
		pygame.draw.rect(self.screen, BOARD_FRAME, frame_rect, border_radius=4)
		pygame.draw.rect(self.screen, BTN_BORDER, frame_rect, width=2, border_radius=4)

		f_coord = pygame.font.SysFont("Arial", 12, bold=True)
		for r in range(8):
			for c in range(8):
				x, y = self.get_screen_pos(r, c)
				# Walnut and Maple inlay
				pygame.draw.rect(self.screen, WHITE_COLOR if (r + c) % 2 == 0 else BLACK_SQ_COLOR, (x, y, self.sq_size, self.sq_size))
				
				# Coordinates with high contrast
				txt_col = (80, 50, 35) if (r + c) % 2 == 0 else (245, 235, 210)
				if (r == 7 and self.player_side == 'w') or (r == 0 and self.player_side == 'b'):
					self.screen.blit(f_coord.render("abcdefgh"[c], True, txt_col), (x + self.sq_size - 12, y + self.sq_size - 14))
				if (c == 0 and self.player_side == 'w') or (c == 7 and self.player_side == 'b'):
					self.screen.blit(f_coord.render("87654321"[r], True, txt_col), (x + 3, y + 2))

	def draw_duck(self, r, c):
		"""Renders the duck sprite centered on a square."""
		x, y = self.get_screen_pos(r, c)
		if 'duck' in self.scaled_images:
			img = self.scaled_images['duck']
			self.screen.blit(img, (x + (self.sq_size - img.get_width()) // 2, y + (self.sq_size - img.get_height()) // 2))

	def draw_game(self, hidden_square=None):
		"""The master render function for active gameplay frames."""
		self.draw_menu_background()

		is_live = (self.view_index == len(self.history) - 1)
		snap = None if is_live else self.history[self.view_index]
		b = self.board if is_live else snap['board']
		last_m = self.last_move_arrow if is_live else snap['last_move']
		p_duck = self.prev_duck_pos if is_live else snap['prev_duck']
		h_pos = self.drag_start if getattr(self, 'dragging', False) and is_live else hidden_square

		self._draw_base_board()

		for r in range(8):
			for c in range(8):
				if last_m and ((r, c) in last_m): self._draw_highlight_square(r, c, LAST_MOVE_COLOR)
				if p_duck and (r, c) == p_duck: self._draw_highlight_square(r, c, LAST_MOVE_COLOR)

				if is_live and not getattr(self, 'promotion_pending', False):
					x, y = self.get_screen_pos(r, c)
					if self.phase == 'move_piece':
						if getattr(self, 'selected_square', None) == (r, c): 
							pygame.draw.rect(self.screen, HIGHLIGHT, (x, y, self.sq_size, self.sq_size))
						if (r, c) in getattr(self, 'valid_moves', []):
							s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
							if b[r][c]: pygame.draw.circle(s, (100, 255, 100, 180), (self.sq_size // 2, self.sq_size // 2), self.sq_size // 2 - 2, 6)
							else: pygame.draw.circle(s, (100, 255, 100, 150), (self.sq_size // 2, self.sq_size // 2), self.sq_size // 6)
							self.screen.blit(s, (x, y))
					elif self.phase == 'move_duck' and not b[r][c] and (r, c) != p_duck:
						s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
						pygame.draw.circle(s, (255, 215, 0, 100), (self.sq_size // 2, self.sq_size // 2), self.sq_size // 5)
						self.screen.blit(s, (x, y))

				if h_pos and (r, c) == h_pos: continue
				if (self.duck_pos if is_live else snap['duck_pos']) == (r, c): self.draw_duck(r, c)

				p = b[r][c]
				if p:
					# Standard check is not present, adding it for consistency
					if p.type == 'K' and self.is_in_check(p.color, b): 
						self._draw_highlight_square(r, c, (235, 60, 60, 180))
					self._draw_piece_sprite(p, *self.get_screen_pos(r, c))

		if getattr(self, 'dragging', False) and self.drag_piece and is_live:
			mx, my = pygame.mouse.get_pos()
			k = 'duck' if self.drag_piece == 'duck' else f"{self.drag_piece.color}{self.drag_piece.type}"
			if k in self.scaled_images: 
				self.screen.blit(self.scaled_images[k], (mx - self.drag_offset[0], my - self.drag_offset[1]))

		self.draw_eval_bar(b)
		self.draw_history_panel()
		self.draw_in_game_hud()
		if getattr(self, 'promotion_pending', False) and is_live: self.draw_promotion_ui()