import pygame
from DuckChess_Game.UI.settings import *
from DuckChess_Game.UI.pieces import Piece
from DuckChess_Game.Logic.constants import *

class EditorInputMixin:
	"""Handles inputs specific to the custom board editor."""

	def handle_editor_input(self, event):
		"""Processes clicks and drags within the editor mode."""
		mx, my = pygame.mouse.get_pos()
		if event.type == pygame.MOUSEBUTTONDOWN:
			if hasattr(self, 'editor_turn_btn') and self.editor_turn_btn.collidepoint((mx, my)):
				self.turn = 'b' if self.turn == 'w' else 'w'
				return
			if hasattr(self, 'editor_play_btn') and self.editor_play_btn.collidepoint((mx, my)):
				if self.validate_editor_board():
					self.state, self.game_mode, self.phase = 'game', 'pvp', 'move_piece'
					self.save_snapshot()
					return
			if hasattr(self, 'editor_clear_btn') and self.editor_clear_btn.collidepoint((mx, my)):
				self.clear_board()
				return
			if hasattr(self, 'editor_menu_btn') and self.editor_menu_btn.collidepoint((mx, my)):
				self.state = 'menu'
				return

			palette_x = self.board_x + (self.sq_size * 8) + (self.side_margin * 2)
			pieces = [KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN]
			for i, p_type in enumerate(pieces):
				wr = pygame.Rect(palette_x, self.board_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
				if wr.collidepoint((mx, my)): 
					self.dragging, self.drag_piece = True, f"w{p_type}"
					return
				
				br = pygame.Rect(palette_x + self.sq_size + 10, self.board_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
				if br.collidepoint((mx, my)): 
					self.dragging, self.drag_piece = True, f"b{p_type}"
					return
			
			dr = pygame.Rect(palette_x, self.board_y + 6 * (self.sq_size + 10), self.sq_size, self.sq_size)
			if dr.collidepoint((mx, my)): 
				self.dragging, self.drag_piece = True, "duck"
				return

			r, c = self.get_board_pos(mx, my)
			if r != -1:
				if self.duck_pos == (r, c):
					self.dragging, self.drag_piece, self.duck_pos = True, "duck", (-1, -1)
				elif self.board[r][c]:
					p = self.board[r][c]
					self.dragging, self.drag_piece, self.board[r][c] = True, f"{p.color}{p.type}", None

		elif event.type == pygame.MOUSEBUTTONUP and getattr(self, 'dragging', False):
			r, c = self.get_board_pos(mx, my)
			if r != -1:
				if self.drag_piece == 'duck': 
					self.duck_pos, self.board[r][c] = (r, c), None
				else: 
					self.board[r][c] = Piece(self.drag_piece[0], self.drag_piece[1:])
			self.dragging, self.drag_piece = False, None