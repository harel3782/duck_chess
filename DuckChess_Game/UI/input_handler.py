import pygame
import os
import sys
from DuckChess_Game.UI.settings import *
from DuckChess_Game.UI.pieces import Piece

class InputHandlerMixin:
	"""Handles all user inputs: mouse clicks, dragging pieces, and keyboard events."""

	def handle_menu_click(self, pos):
		"""Main Menu interactions with standard OS file dialog for replays."""
		if not hasattr(self, 'menu_rects'): return
		
		for key, rect in self.menu_rects.items():
			if rect.collidepoint(pos):
				if hasattr(self, 'play_sound'): self.play_sound('move')
				
				if key == 'white':
					self.game_mode = 'white_ai'; self.player_side = 'w'; self.reset_game_state(); self.state = 'game'
				elif key == 'black':
					self.game_mode = 'black_ai'; self.player_side = 'b'; self.reset_game_state(); self.state = 'game'
				elif key == 'pvp':
					self.game_mode = 'pvp'; self.player_side = 'w'; self.reset_game_state(); self.state = 'game'
				elif key == 'edit':
					self.clear_board(); self.init_board(); self.state = 'edit'
				elif key == 'replay':
					# Open standard OS file dialog
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
					pygame.quit(); sys.exit()

	def handle_mouse_down(self, pos):
		if self.promotion_pending: return

		# Navigation Arrows (Synced with Log Panel locations)
		if self.nav_btns['start'].collidepoint(pos): self.view_index = 0; return
		if self.nav_btns['prev'].collidepoint(pos): self.view_index = max(0, self.view_index - 1); return
		if self.nav_btns['next'].collidepoint(pos): self.view_index = min(len(self.history) - 1, self.view_index + 1); return
		if self.nav_btns['end'].collidepoint(pos): self.view_index = len(self.history) - 1; return

		# HUD Buttons
		if self.restart_btn_rect.collidepoint(pos): self.reset_game_state(); return
		if self.eval_btn_rect.collidepoint(pos): self.show_eval = not self.show_eval; return
		if self.menu_btn_rect.collidepoint(pos): self.state = 'menu'; return
		if self.game_mode == 'pvp' and hasattr(self, 'flip_btn_rect') and self.flip_btn_rect.collidepoint(pos):
			self.player_side = 'b' if self.player_side == 'w' else 'w'; return

		is_live = (self.view_index == len(self.history) - 1)
		if not is_live or self.game_over or self.waiting_for_ai: return

		r, c = self.get_board_pos(pos[0], pos[1])
		if r == -1: return

		if self.phase == 'move_piece':
			piece = self.board[r][c]
			if piece and piece.color == self.turn:
				self.dragging = True; self.drag_piece = piece; self.drag_start = (r, c)
				px, py = self.get_screen_pos(r, c)
				self.drag_offset = (pos[0] - px, pos[1] - py)
				self.selected_square = (r, c)
				self.valid_moves = self.get_piece_legal_moves(r, c)
			elif self.selected_square and (r, c) in self.valid_moves:
				self.execute_move(self.selected_square, (r, c))
				self.selected_square = None; self.valid_moves = []
		elif self.phase == 'move_duck':
			if not self.board[r][c] and (r, c) != self.prev_duck_pos:
				self.place_duck((r, c))

	def handle_mouse_up(self, pos):
		if not self.dragging: return
		r, c = self.get_board_pos(pos[0], pos[1])
		if r != -1 and self.phase == 'move_piece' and self.drag_piece != 'duck':
			if (r, c) in self.valid_moves:
				self.execute_move(self.drag_start, (r, c), animated=False)
		self.dragging = False; self.drag_piece = None; self.drag_start = None

	def handle_keyboard(self, event):
		if event.key == pygame.K_LEFT: self.view_index = max(0, self.view_index - 1)
		elif event.key == pygame.K_RIGHT: self.view_index = min(len(self.history) - 1, self.view_index + 1)

	def handle_editor_input(self, event):
		"""Restored full editor functionality: Dragging from palette and board."""
		mx, my = pygame.mouse.get_pos()
		if event.type == pygame.MOUSEBUTTONDOWN:
			# Editor HUD buttons
			if hasattr(self, 'editor_turn_btn') and self.editor_turn_btn.collidepoint((mx, my)):
				self.turn = 'b' if self.turn == 'w' else 'w'; return
			if hasattr(self, 'editor_play_btn') and self.editor_play_btn.collidepoint((mx, my)):
				if self.validate_editor_board():
					self.state = 'game'; self.game_mode = 'pvp'; self.save_snapshot(); return
			if hasattr(self, 'editor_clear_btn') and self.editor_clear_btn.collidepoint((mx, my)):
				self.clear_board(); return
			if hasattr(self, 'editor_menu_btn') and self.editor_menu_btn.collidepoint((mx, my)):
				self.state = 'menu'; return

			# Palette Check (Right Side)
			palette_x = self.board_x + (self.sq_size * 8) + (self.side_margin * 2)
			pieces = [KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN]
			for i, p_type in enumerate(pieces):
				# White Column
				wr = pygame.Rect(palette_x, self.board_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
				if wr.collidepoint((mx, my)): self.dragging = True; self.drag_piece = f"w{p_type}"; return
				# Black Column
				br = pygame.Rect(palette_x + self.sq_size + 10, self.board_y + i * (self.sq_size + 10), self.sq_size, self.sq_size)
				if br.collidepoint((mx, my)): self.dragging = True; self.drag_piece = f"b{p_type}"; return
			# Duck in Palette
			dr = pygame.Rect(palette_x, self.board_y + 6 * (self.sq_size + 10), self.sq_size, self.sq_size)
			if dr.collidepoint((mx, my)): self.dragging = True; self.drag_piece = "duck"; return

			# Board Interaction
			r, c = self.get_board_pos(mx, my)
			if r != -1:
				if self.duck_pos == (r, c):
					self.dragging = True; self.drag_piece = "duck"; self.duck_pos = (-1, -1)
				elif self.board[r][c]:
					p = self.board[r][c]
					self.dragging = True; self.drag_piece = f"{p.color}{p.type}"; self.board[r][c] = None

		elif event.type == pygame.MOUSEBUTTONUP and self.dragging:
			r, c = self.get_board_pos(mx, my)
			if r != -1:
				if self.drag_piece == 'duck': self.duck_pos = (r, c); self.board[r][c] = None
				else: self.board[r][c] = Piece(self.drag_piece[0], self.drag_piece[1:])
			self.dragging = False; self.drag_piece = None