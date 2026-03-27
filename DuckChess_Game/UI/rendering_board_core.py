import pygame
from DuckChess_Game.UI.settings import *

class BoardCoreRenderingMixin:
	"""Handles the physical 8x8 grid rendering with static surface caching and King threat highlights."""

	def _draw_base_board(self):
		"""Draws the walnut and maple inlay squares using a cached surface without the yellow border."""
		if not hasattr(self, '_cached_board_surface') or getattr(self, '_cached_sq_size', 0) != self.sq_size:
			self._cached_sq_size = self.sq_size
			surf_size = self.sq_size * 8 + 30
			self._cached_board_surface = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
			
			frame_rect = pygame.Rect(0, 0, surf_size, surf_size)
			pygame.draw.rect(self._cached_board_surface, BOARD_FRAME, frame_rect, border_radius=4)
			
			# Removed the secondary yellow border line completely for a cleaner look

			f_coord = pygame.font.SysFont("Arial", 11, bold=True)
			for r in range(8):
				for c in range(8):
					dr, dc = (7 - r, 7 - c) if self.player_side == 'b' else (r, c)
					lx, ly = 15 + dc * self.sq_size, 15 + dr * self.sq_size
					
					pygame.draw.rect(self._cached_board_surface, WHITE_COLOR if (r + c) % 2 == 0 else BLACK_SQ_COLOR, (lx, ly, self.sq_size, self.sq_size))
					
					txt_col = (80, 50, 35) if (r + c) % 2 == 0 else (245, 235, 210)
					if (r == 7 and self.player_side == 'w') or (r == 0 and self.player_side == 'b'):
						lbl = f_coord.render("abcdefgh"[c], True, txt_col)
						self._cached_board_surface.blit(lbl, (lx + self.sq_size - 10, ly + self.sq_size - 12))
					if (c == 0 and self.player_side == 'w') or (c == 7 and self.player_side == 'b'):
						lbl = f_coord.render("87654321"[r], True, txt_col)
						self._cached_board_surface.blit(lbl, (lx + 3, ly + 2))

		self.screen.blit(self._cached_board_surface, (self.board_x - 15, self.board_y - 15))

	def draw_game(self, hidden_square=None):
		"""Master render function with Duck Chess rules and optimized visual indicators."""
		self.draw_menu_background()
		is_live = (self.view_index == len(self.history) - 1)
		snap = None if is_live else self.history[self.view_index]
		b = self.board if is_live else snap['board']
		last_m = self.last_move_arrow if is_live else snap['last_move']
		p_duck = self.prev_duck_pos if is_live else snap['prev_duck']
		h_pos = self.drag_start if getattr(self, 'dragging', False) and is_live else hidden_square

		self._draw_base_board()

		w_in_check = self.is_in_check('w', b)
		b_in_check = self.is_in_check('b', b)

		is_player_turn = (getattr(self, 'game_mode', '') == 'pvp' or self.turn == self.player_side)

		for r in range(8):
			for c in range(8):
				# Draw last move highlights for pieces
				if last_m and ((r, c) in last_m): self._draw_highlight_square(r, c, LAST_MOVE_COLOR)
				if p_duck and (r, c) == p_duck: self._draw_highlight_square(r, c, LAST_MOVE_COLOR)

				if is_live and is_player_turn and not getattr(self, 'promotion_pending', False):
					x, y = self.get_screen_pos(r, c)
					if self.phase == 'move_piece':
						if getattr(self, 'selected_square', None) == (r, c): 
							self._draw_highlight_square(r, c, HIGHLIGHT)
						if (r, c) in getattr(self, 'valid_moves', []):
							s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
							if b[r][c]: pygame.draw.circle(s, VALID_CAPTURE_RED, (self.sq_size // 2, self.sq_size // 2), self.sq_size // 2 - 4, 5)
							else: pygame.draw.circle(s, VALID_MOVE_ORANGE, (self.sq_size // 2, self.sq_size // 2), self.sq_size // 6)
							self.screen.blit(s, (x, y))
					elif self.phase == 'move_duck' and not b[r][c] and (r, c) != p_duck:
						s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
						pygame.draw.circle(s, VALID_MOVE_ORANGE, (self.sq_size // 2, self.sq_size // 2), self.sq_size // 6)
						self.screen.blit(s, (x, y))

				if h_pos and (r, c) == h_pos: continue
				if (self.duck_pos if is_live else snap['duck_pos']) == (r, c): self.draw_duck(r, c)

				p = b[r][c]
				if p:
					if p.type == 'K':
						if (p.color == 'w' and w_in_check) or (p.color == 'b' and b_in_check):
							self._draw_highlight_square(r, c, (200, 50, 50, 160))
					self._draw_piece_sprite(p, *self.get_screen_pos(r, c))

		if getattr(self, 'dragging', False) and self.drag_piece and is_live:
			mx, my = pygame.mouse.get_pos()
			k = 'duck' if self.drag_piece == 'duck' else f"{self.drag_piece.color}{self.drag_piece.type}"
			if k in self.scaled_images: 
				self.screen.blit(self.scaled_images[k], (mx - self.drag_offset[0], my - self.drag_offset[1]))

		if getattr(self, 'show_eval', True): self.draw_eval_bar(b)
		self.draw_history_panel()
		self.draw_in_game_hud()

	def draw_duck(self, r, c):
		"""Renders the duck sprite centered on a square."""
		x, y = self.get_screen_pos(r, c)
		if 'duck' in self.scaled_images:
			img = self.scaled_images['duck']
			self.screen.blit(img, (x + (self.sq_size - img.get_width()) // 2, y + (self.sq_size - img.get_height()) // 2))