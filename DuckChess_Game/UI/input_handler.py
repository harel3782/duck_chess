import pygame
from DuckChess_Game.UI.settings import *
from DuckChess_Game.UI.pieces import Piece

class InputHandlerMixin:
	"""Handles all user inputs: mouse clicks, dragging pieces, and keyboard events."""

	def handle_mouse_down(self, pos):
		if self.promotion_pending: return

		# Navigation
		if self.nav_btns['start'].collidepoint(pos): self.view_index = 0; return
		if self.nav_btns['prev'].collidepoint(pos): self.view_index = max(0, self.view_index - 1); return
		if self.nav_btns['next'].collidepoint(pos): self.view_index = min(len(self.history) - 1, self.view_index + 1); return
		if self.nav_btns['end'].collidepoint(pos): self.view_index = len(self.history) - 1; return

		# Control Buttons
		if self.restart_btn_rect.collidepoint(pos):
			self.reset_game_state()
			return
		if self.eval_btn_rect.collidepoint(pos):
			self.show_eval = not self.show_eval
			return
		if self.menu_btn_rect.collidepoint(pos): self.state = 'menu'; return
		if self.game_mode == 'pvp' and self.flip_btn_rect.collidepoint(pos):
			self.player_side = 'b' if self.player_side == 'w' else 'w'; return

		is_live = (self.view_index == len(self.history) - 1)
		if not is_live or self.game_over or self.waiting_for_ai: return

		r, c = self.get_board_pos(pos[0], pos[1])
		if r == -1: return

		if self.phase == 'move_piece':
			piece = self.board[r][c]

			if piece and piece.color == self.turn:
				self.dragging = True
				self.drag_piece = piece
				self.drag_start = (r, c)
				px, py = self.get_screen_pos(r, c)
				self.drag_offset = (pos[0] - px, pos[1] - py)
				self.selected_square = (r, c)
				self.valid_moves = self.get_piece_legal_moves(r, c)

			elif self.selected_square and (r, c) in self.valid_moves:
				self.execute_move(self.selected_square, (r, c))
				self.selected_square = None
				self.valid_moves = []

			else:
				self.selected_square = None
				self.valid_moves = []

		elif self.phase == 'move_duck':
			if (r, c) == self.duck_pos:
				self.dragging = True
				self.drag_piece = 'duck'
				self.drag_start = (r, c)
				px, py = self.get_screen_pos(r, c)
				self.drag_offset = (pos[0] - px, pos[1] - py)

			elif not self.board[r][c] and (r, c) != self.prev_duck_pos:
				self.place_duck((r, c))

	def handle_mouse_up(self, pos):
		if not self.dragging: return

		r, c = self.get_board_pos(pos[0], pos[1])

		if r != -1:
			if self.phase == 'move_piece' and self.drag_piece != 'duck':
				if (r, c) in self.valid_moves:
					self.execute_move(self.drag_start, (r, c), animated=False)
					self.selected_square = None
					self.valid_moves = []
				elif (r, c) == self.drag_start:
					pass
				else:
					self.selected_square = None
					self.valid_moves = []

			elif self.phase == 'move_duck' and self.drag_piece == 'duck':
				if not self.board[r][c] and (r, c) != self.prev_duck_pos:
					self.place_duck((r, c), animated=False)

		self.dragging = False
		self.drag_piece = None
		self.drag_start = None

	def handle_keyboard(self, event):
		if event.key == pygame.K_LEFT:
			self.view_index = max(0, self.view_index - 1)
		elif event.key == pygame.K_RIGHT:
			self.view_index = min(len(self.history) - 1, self.view_index + 1)

	def handle_editor_input(self, event):
		mx, my = pygame.mouse.get_pos()

		if event.type == pygame.MOUSEBUTTONDOWN:
			# --- Turn Toggle ---
			if hasattr(self, 'editor_turn_btn') and self.editor_turn_btn.collidepoint((mx, my)):
				self.turn = 'b' if self.turn == 'w' else 'w'
				return

			# --- UI Buttons ---
			if hasattr(self, 'editor_play_btn') and self.editor_play_btn.collidepoint((mx, my)):
				if self.validate_editor_board():
					self.state = 'game'
					self.game_mode = 'pvp'
					self.phase = 'move_piece'
					self.save_snapshot()
					return

			if hasattr(self, 'editor_clear_btn') and self.editor_clear_btn.collidepoint((mx, my)):
				self.clear_board()
				return

			if hasattr(self, 'editor_menu_btn') and self.editor_menu_btn.collidepoint((mx, my)):
				self.state = 'menu'
				return

			# --- Palette Interaction ---
			palette_x = self.board_x + self.sq_size * 8 + 40
			start_y = self.board_y
			white_pieces = [KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN]

			# White Column
			for i, p_type in enumerate(white_pieces):
				r = pygame.Rect(palette_x, start_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
				if r.collidepoint((mx, my)):
					self.dragging = True
					self.drag_piece = f"w{p_type}"
					return

			# Black Column
			for i, p_type in enumerate(white_pieces):
				r = pygame.Rect(palette_x + self.sq_size + 10, start_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
				if r.collidepoint((mx, my)):
					self.dragging = True
					self.drag_piece = f"b{p_type}"
					return

			# Duck
			y_duck = start_y + 6 * (self.sq_size + 10)
			r_duck = pygame.Rect(palette_x, y_duck, self.sq_size, self.sq_size)
			if r_duck.collidepoint((mx, my)):
				self.dragging = True
				self.drag_piece = "duck"
				return

			# --- Board Interaction ---
			r, c = self.get_board_pos(mx, my)
			if r != -1:
				p = self.board[r][c]
				if self.duck_pos == (r, c):
					self.dragging = True
					self.drag_piece = "duck"
					self.duck_pos = (-1, -1)
				elif p:
					self.dragging = True
					self.drag_piece = f"{p.color}{p.type}"
					self.board[r][c] = None

		elif event.type == pygame.MOUSEBUTTONUP:
			if self.dragging:
				r, c = self.get_board_pos(mx, my)
				if r != -1:
					if self.drag_piece == 'duck':
						self.duck_pos = (r, c)
						self.board[r][c] = None
					else:
						color = self.drag_piece[0]
						ptype = self.drag_piece[1:]
						self.board[r][c] = Piece(color, ptype)
						if self.duck_pos == (r, c): self.duck_pos = (-1, -1)
				self.dragging = False
				self.drag_piece = None