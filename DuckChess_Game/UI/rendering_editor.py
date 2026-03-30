import pygame
from DuckChess_Game.UI.settings import *
from DuckChess_Game.Logic.constants import *

class EditorRenderingMixin:
	"""Handles the rendering of the board editor and its tools."""

	def draw_editor(self):
		"""Renders the custom board builder interface."""
		self.draw_menu_background()

		# Main Board Area
		pygame.draw.rect(self.screen, (20, 20, 20), (self.board_x - 2, self.board_y - 2, self.sq_size * 8 + 4, self.sq_size * 8 + 4), width=2)
		self._draw_base_board()

		for r in range(8):
			for c in range(8):
				if self.duck_pos == (r, c): self.draw_duck(r, c)
				if self.board[r][c]: self._draw_piece_sprite(self.board[r][c], *self.get_screen_pos(r, c))

		# Piece Palette
		px = self.board_x + self.sq_size * 8 + 40
		pieces = [KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN]
		mouse = pygame.mouse.get_pos()

		for col_idx, color_prefix in enumerate(['w', 'b']):
			for i, p_type in enumerate(pieces):
				y = self.board_y + i * (self.sq_size + 10)
				x = px + (self.sq_size + 10) * col_idx
				key = f"{color_prefix}{p_type}"
				if key in self.scaled_images:
					if pygame.Rect(x, y, self.sq_size, self.sq_size).collidepoint(mouse):
						pygame.draw.rect(self.screen, (255, 255, 255, 50), (x, y, self.sq_size, self.sq_size))
					self.screen.blit(self.scaled_images[key], (x, y))

		# Duck and Trash in Palette
		y_misc = self.board_y + 6 * (self.sq_size + 10)
		if 'duck' in self.scaled_images: self.screen.blit(self.scaled_images['duck'], (px, y_misc))
		
		trash = pygame.Rect(px + self.sq_size + 10, y_misc, self.sq_size, self.sq_size)
		pygame.draw.rect(self.screen, (200, 50, 50), trash, border_radius=4)
		txt = self.font_ui.render("CLR", True, (255, 255, 255))
		self.screen.blit(txt, txt.get_rect(center=trash.center))

		# Dragging Ghost
		if getattr(self, 'dragging', False) and getattr(self, 'drag_piece', None):
			k = self.drag_piece
			if k in self.scaled_images: self.screen.blit(self.scaled_images[k], (mouse[0] - self.sq_size // 2, mouse[1] - self.sq_size // 2))

		# Editor HUD Controls
		hud = pygame.Rect(20, self.screen_h - 70, self.screen_w - 40, 60)
		self.draw_glass_panel(hud)

		valid = self.validate_editor_board()
		self.screen.blit(self.font_status.render("EDITOR: Ready" if valid else "EDITOR MODE", True, (50, 200, 50) if valid else (200, 50, 50)), (40, self.screen_h - 50))

		self.editor_turn_btn = pygame.Rect(self.screen_w - 560, self.screen_h - 58, 140, 36)
		turn_txt = "Turn: WHITE" if self.turn == 'w' else "Turn: BLACK"
		
		# Now using the standard premium HUD button format
		if hasattr(self, 'draw_hud_button'):
			self.draw_hud_button(self.editor_turn_btn, turn_txt, self.editor_turn_btn.collidepoint(mouse))
		else:
			self.draw_styled_button(self.editor_turn_btn, turn_txt, self.editor_turn_btn.collidepoint(mouse))

		for lbl, btn in [("MENU", self.editor_menu_btn), ("CLEAR", self.editor_clear_btn), ("PLAY", self.editor_play_btn)]:
			btn.update(self.screen_w - {"MENU":410, "CLEAR":280, "PLAY":150}[lbl], self.screen_h - 58, 120, 36)
			if lbl != "PLAY" or valid: 
				if hasattr(self, 'draw_hud_button'):
					self.draw_hud_button(btn, lbl, btn.collidepoint(mouse))
				else:
					self.draw_styled_button(btn, lbl, btn.collidepoint(mouse))