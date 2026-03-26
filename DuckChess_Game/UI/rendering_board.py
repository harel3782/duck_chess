import pygame
import math
from DuckChess_Game.UI.settings import *

class BoardRenderingMixin:
	"""Handles board, piece, duck rendering, and the Editor interface."""

	def get_rect(self, r, c):
		x, y = self.get_screen_pos(r, c)
		return pygame.Rect(x, y, self.sq_size, self.sq_size)

	def draw_translucent_rect(self, surface, color, rect, border_radius=0):
		s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
		pygame.draw.rect(s, color, (0, 0, rect.width, rect.height), border_radius=border_radius)
		surface.blit(s, rect.topleft)

	def draw_translucent_circle(self, surface, color, center, radius, width=0):
		s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
		pygame.draw.circle(s, color, (radius, radius), radius, width)
		surface.blit(s, (center[0] - radius, center[1] - radius))

	def _draw_base_board(self, board_surface):
		for r in range(8):
			for c in range(8):
				color = COLOR_SQ_LIGHT if (r + c) % 2 == 0 else COLOR_SQ_DARK
				rect = pygame.Rect(c * self.sq_size, r * self.sq_size, self.sq_size, self.sq_size)
				pygame.draw.rect(board_surface, color, rect)

	def _draw_neon_piece(self, p, r, c):
		x, y = self.get_screen_pos(r, c)
		key = f"{p.color}{p.type}"
		if key in self.scaled_images:
			img = self.scaled_images[key]
			glow_col = COLOR_ACCENT_WHITE if p.color == 'w' else COLOR_ACCENT_BLACK
			glow_surf = img.copy()
			glow_surf.fill(glow_col[:3], special_flags=pygame.BLEND_RGBA_MULT)
			pulse = 180 + 75 * math.sin(pygame.time.get_ticks() * 0.005)
			glow_surf.set_alpha(int(pulse * 0.4))
			self.screen.blit(glow_surf, (x - 2, y - 2))
			self.screen.blit(img, (x, y))

	def draw_editor(self):
		"""Restored Editor view with palette and HUD."""
		self.draw_menu_background()
		bw = self.sq_size * 8
		board_rect = pygame.Rect(self.board_x, self.board_y, bw, bw)
		self.draw_glass_panel(board_rect, border_radius=10)
		
		# Draw Base Board
		board_surf = pygame.Surface((bw, bw))
		self._draw_base_board(board_surf)
		self.screen.blit(board_surf, board_rect.topleft)

		# Piece Palette [cite: 96]
		palette_x = self.board_x + bw + (self.side_margin * 2)
		pieces = [KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN]
		for i, p_type in enumerate(pieces):
			for col_idx, color in enumerate(['w', 'b']):
				key = f"{color}{p_type}"
				if key in self.scaled_images:
					r = pygame.Rect(palette_x + col_idx * (self.sq_size + 10), self.board_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
					if r.collidepoint(pygame.mouse.get_pos()): self.draw_translucent_rect(self.screen, COLOR_HIGHLIGHT, r, 5)
					self.screen.blit(self.scaled_images[key], r.topleft)

		# Board Content & Floating Piece
		for r in range(8):
			for c in range(8):
				if self.duck_pos == (r, c):
					self.screen.blit(self.scaled_images['duck'], self.get_rect(r, c).topleft)
				p = self.board[r][c]
				if p: self._draw_neon_piece(p, r, c)

		if hasattr(self, 'dragging') and self.dragging and self.drag_piece:
			mx, my = pygame.mouse.get_pos()
			img_key = self.drag_piece if isinstance(self.drag_piece, str) else f"{self.drag_piece.color}{self.drag_piece.type}"
			if img_key in self.scaled_images:
				self.screen.blit(self.scaled_images[img_key], (mx - self.sq_size // 2, my - self.sq_size // 2))

		self.draw_in_game_hud()

	def draw_game(self, hidden_square=None):
		self.draw_menu_background()
		is_live = (self.view_index == len(self.history) - 1)
		# Load from history or current [cite: 97, 98]
		snap = self.history[self.view_index] if not is_live else None
		board = self.board if is_live else snap['board']
		d_pos = self.duck_pos if is_live else snap['duck_pos']
		
		# Board and Glass Panel
		bw = self.sq_size * 8
		self.draw_glass_panel(pygame.Rect(self.board_x - 10, self.board_y - 10, bw + 20, bw + 20), 10)
		board_surf = pygame.Surface((bw, bw))
		self._draw_base_board(board_surf); self.screen.blit(board_surf, (self.board_x, self.board_y))

		for r in range(8):
			for c in range(8):
				# Markers and Highlights [cite: 98]
				if is_live and self.phase == 'move_piece' and self.selected_square == (r, c) and not self.dragging:
					self.draw_translucent_rect(self.screen, COLOR_HIGHLIGHT, self.get_rect(r, c), 5)
				if is_live and self.phase == 'move_piece' and (r, c) in self.valid_moves and not self.promotion_pending:
					x, y = self.get_screen_pos(r, c)
					if board[r][c]: self.draw_translucent_circle(self.screen, (255, 50, 50, 180), (x+self.sq_size//2, y+self.sq_size//2), self.sq_size//2-2, 4)
					else: self.draw_translucent_circle(self.screen, (0, 255, 255, 150), (x+self.sq_size//2, y+self.sq_size//2), self.sq_size//8)
				
				# Render Pieces/Duck
				if d_pos == (r, c) and 'duck' in self.scaled_images:
					self.screen.blit(self.scaled_images['duck'], self.get_rect(r, c).topleft)
				p = board[r][c]
				if p and (r, c) != hidden_square:
					if p.type == 'K' and self.is_in_check(p.color, board):
						pygame.draw.rect(self.screen, (200, 30, 30), self.get_rect(r, c))
					self._draw_neon_piece(p, r, c)

		if hasattr(self, 'dragging') and self.dragging and is_live:
			mx, my = pygame.mouse.get_pos()
			k = 'duck' if self.drag_piece == 'duck' else f"{self.drag_piece.color}{self.drag_piece.type}"
			self.screen.blit(self.scaled_images[k], (mx - self.sq_size // 2, my - self.sq_size // 2))

		if self.show_eval: self.draw_eval_bar(board)
		self.draw_history_panel_2_column(); self.draw_in_game_hud()
		if self.promotion_pending and is_live: self.draw_promotion_ui()

	def animate_move_visual(self, start, end, piece, is_duck=False):
		if self.view_index != len(self.history) - 1: return
		x1, y1 = self.get_screen_pos(start[0], start[1])
		x2, y2 = self.get_screen_pos(end[0], end[1])
		key = 'duck' if is_duck else f"{piece.color}{piece.type}"
		img = self.scaled_images.get(key)
		if not img: return
		st = pygame.time.get_ticks()
		while True:
			el = pygame.time.get_ticks() - st
			if el >= ANIMATION_SPEED: break
			prog = 1 - math.pow(1 - (el / ANIMATION_SPEED), 3)
			self.draw_game(hidden_square=start)
			self.screen.blit(img, (x1 + (x2 - x1) * prog, y1 + (y2 - y1) * prog))
			pygame.display.flip(); pygame.time.Clock().tick(ANIMATION_FPS)