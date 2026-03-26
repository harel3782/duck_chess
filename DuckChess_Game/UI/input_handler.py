import pygame
import sys
from DuckChess_Game.UI.settings import *
from DuckChess_Game.UI.pieces import Piece

class InputHandlerMixin:
	"""Handles all user inputs systematically: mouse clicks, dragging pieces, and keyboard events."""

	def process_events(self, events):
		"""The single entry point for all pygame events."""
		for event in events:
			if event.type == pygame.QUIT:
				pygame.quit()
				sys.exit()

			if event.type == pygame.VIDEORESIZE:
				self.resize_layout(event.w, event.h)

			if self.state == 'menu':
				if event.type == pygame.MOUSEBUTTONDOWN:
					self.handle_menu_click(event.pos)
					
			elif self.state == 'edit':
				self.handle_editor_input(event)
				
			elif self.state == 'game':
				if event.type == pygame.MOUSEBUTTONDOWN:
					if getattr(self, 'promotion_pending', False):
						self.handle_promotion_click(event.pos)
					else:
						self.handle_mouse_down(event.pos)
				elif event.type == pygame.MOUSEBUTTONUP:
					self.handle_mouse_up(event.pos)
				elif event.type == pygame.KEYDOWN:
					self.handle_keyboard(event)

	def handle_menu_click(self, pos):
		"""Main Menu interactions with standard OS file dialog for replays."""
		if not hasattr(self, 'menu_rects'): return
		
		for key, rect in self.menu_rects.items():
			if rect.collidepoint(pos):
				if hasattr(self, 'play_sound'): self.play_sound('move')
				
				if key == 'white':
					self.game_mode, self.player_side, self.state = 'white_ai', 'w', 'game'
					self.reset_game_state()
				elif key == 'black':
					self.game_mode, self.player_side, self.state = 'black_ai', 'b', 'game'
					self.reset_game_state()
				elif key == 'pvp':
					self.game_mode, self.player_side, self.state = 'pvp', 'w', 'game'
					self.reset_game_state()
				elif key == 'edit':
					self.clear_board()
					self.init_board()
					self.state = 'edit'
				elif key == 'replay':
					import tkinter as tk
					from tkinter import filedialog
					root = tk.Tk(); root.withdraw()
					file_path = filedialog.askopenfilename(
						title="Select Duck Chess Replay",
						filetypes=[("Replay Files", "*.pkl"), ("All Files", "*.*")]
					)
					root.destroy()
					if file_path:
						if hasattr(self, 'play_sound'): self.play_sound('notify')
						self.load_replay_file(file_path)
				elif key == 'quit':
					pygame.quit()
					sys.exit()

	def handle_promotion_click(self, pos):
		"""Handles piece selection during a pawn promotion."""
		for rect, p_type in self.get_promotion_rects():
			if rect.collidepoint(pos):
				self.promote_pawn(p_type)
				break

	def handle_mouse_down(self, pos):
		"""Handles clicks during active gameplay."""
		# Navigation Arrows
		if self.nav_btns['start'].collidepoint(pos): self.view_index = 0; return
		if self.nav_btns['prev'].collidepoint(pos): self.view_index = max(0, self.view_index - 1); return
		if self.nav_btns['next'].collidepoint(pos): self.view_index = min(len(self.history) - 1, self.view_index + 1); return
		if self.nav_btns['end'].collidepoint(pos): self.view_index = len(self.history) - 1; return

		# HUD Buttons
		if self.restart_btn_rect.collidepoint(pos): self.reset_game_state(); return
		if hasattr(self, 'eval_btn_rect') and self.eval_btn_rect.collidepoint(pos): self.show_eval = not self.show_eval; return
		if self.menu_btn_rect.collidepoint(pos): self.state = 'menu'; return
		if self.game_mode == 'pvp' and hasattr(self, 'flip_btn_rect') and self.flip_btn_rect.collidepoint(pos):
			self.player_side = 'b' if self.player_side == 'w' else 'w'; return

		is_live = (self.view_index == len(self.history) - 1)
		if not is_live or self.game_over or getattr(self, 'waiting_for_ai', False): return

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
		"""Handles piece dropping and click-to-move mechanics."""
		if not getattr(self, 'dragging', False): return
		
		r, c = self.get_board_pos(pos[0], pos[1])
		if r != -1:
			if self.phase == 'move_piece' and self.drag_piece != 'duck':
				if (r, c) in self.valid_moves:
					self.execute_move(self.drag_start, (r, c), animated=False)
					self.selected_square = None
					self.valid_moves = []
				elif (r, c) == self.drag_start:
					# It was just a click, preserve the selection
					pass
				else:
					# Clicked/dropped on an invalid square, clear selection
					self.selected_square = None
					self.valid_moves = []
					
			elif self.phase == 'move_duck' and self.drag_piece == 'duck':
				if not self.board[r][c] and (r, c) != self.prev_duck_pos:
					self.place_duck((r, c), animated=False)

		self.dragging = False
		self.drag_piece = None
		self.drag_start = None

	def handle_keyboard(self, event):
		"""Handles keyboard shortcuts."""
		if event.key == pygame.K_LEFT: self.view_index = max(0, self.view_index - 1)
		elif event.key == pygame.K_RIGHT: self.view_index = min(len(self.history) - 1, self.view_index + 1)

	def handle_editor_input(self, event):
		"""Handles inputs specific to the board editor."""
		mx, my = pygame.mouse.get_pos()
		if event.type == pygame.MOUSEBUTTONDOWN:
			if hasattr(self, 'editor_turn_btn') and self.editor_turn_btn.collidepoint((mx, my)):
				self.turn = 'b' if self.turn == 'w' else 'w'; return
			if hasattr(self, 'editor_play_btn') and self.editor_play_btn.collidepoint((mx, my)):
				if self.validate_editor_board():
					self.state, self.game_mode, self.phase = 'game', 'pvp', 'move_piece'
					self.save_snapshot()
					return
			if hasattr(self, 'editor_clear_btn') and self.editor_clear_btn.collidepoint((mx, my)):
				self.clear_board(); return
			if hasattr(self, 'editor_menu_btn') and self.editor_menu_btn.collidepoint((mx, my)):
				self.state = 'menu'; return

			palette_x = self.board_x + (self.sq_size * 8) + (self.side_margin * 2)
			pieces = [KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN]
			for i, p_type in enumerate(pieces):
				wr = pygame.Rect(palette_x, self.board_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
				if wr.collidepoint((mx, my)): self.dragging, self.drag_piece = True, f"w{p_type}"; return
				br = pygame.Rect(palette_x + self.sq_size + 10, self.board_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
				if br.collidepoint((mx, my)): self.dragging, self.drag_piece = True, f"b{p_type}"; return
			
			dr = pygame.Rect(palette_x, self.board_y + 6 * (self.sq_size + 10), self.sq_size, self.sq_size)
			if dr.collidepoint((mx, my)): self.dragging, self.drag_piece = True, "duck"; return

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
				if self.drag_piece == 'duck': self.duck_pos, self.board[r][c] = (r, c), None
				else: self.board[r][c] = Piece(self.drag_piece[0], self.drag_piece[1:])
			self.dragging, self.drag_piece = False, None