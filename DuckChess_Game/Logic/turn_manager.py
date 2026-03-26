import pygame
from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.notation_helper import NotationHelper
from DuckChess_Game.Logic.move_executor import MoveExecutor

class TurnManagerMixin:
	"""Handles piece movement, duck placement, and AI turns."""

	def execute_move(self, start, end, animated=True):
		"""Executes a piece move, plays sounds, checks for promotion, and transitions phases."""
		p = self.board[start[0]][start[1]]
		
		# Safety net: If replay desyncs or empty square is selected
		if not p:
			print(f"Warning: Attempted to move an empty square at {start}")
			return

		move_str = p.type if p.type != PAWN else ""
		is_capture = self.board[end[0]][end[1]] is not None
		if is_capture: move_str += "x"
		move_str += NotationHelper.get_notation_coords(end[0], end[1])
		self.current_move_str = move_str

		is_castle = (p.type == KING and abs(start[1] - end[1]) == 2)
		sound_to_play = 'capture' if is_capture else ('castle' if is_castle else 'move')

		if animated and hasattr(self, 'animate_move_visual'):
			self.animate_move_visual(start, end, p, is_duck=False)

		executor = MoveExecutor()
		captured = executor.execute_piece_move(self.board, start, end)

		if hasattr(self, 'play_sound') and getattr(self, 'game_mode', '') != 'replay':
			self.play_sound(sound_to_play)

		if captured and captured.type == KING:
			self.game_over = True
			self.winner = self.turn
			self.save_snapshot()
			if hasattr(self, 'play_sound') and getattr(self, 'game_mode', '') != 'replay':
				self.play_sound('game_over')
		else:
			promote_rank = 0 if p.color == 'w' else 7
			if p.type == PAWN and end[0] == promote_rank:
				game_mode = getattr(self, 'game_mode', '')
				# FIX: Added 'replay' to auto-promote so it doesn't wait for UI input and desync phases
				is_auto = game_mode in ('rl_training', 'replay') or \
							 (game_mode == 'white_ai' and self.turn == 'b') or \
							 (game_mode == 'black_ai' and self.turn == 'w')
				
				if is_auto:
					p.type = QUEEN
					self.current_move_str += "=Q"
					if hasattr(self, 'play_sound') and game_mode != 'replay': 
						self.play_sound('promote')
					self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'
				else:
					self.promotion_pending = True
					self.promotion_coords = (end[0], end[1])
					if hasattr(self, 'play_sound'): self.play_sound('notify')
			else:
				self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'

	def promote_pawn(self, type_char):
		"""Called by the UI when the player selects a promotion piece."""
		if not getattr(self, 'promotion_coords', None): return
		
		r, c = self.promotion_coords
		self.board[r][c].type = type_char
		self.current_move_str += f"={type_char}"
		
		if hasattr(self, 'is_in_check') and self.is_in_check('b' if self.turn == 'w' else 'w'):
			if "+" not in self.current_move_str: self.current_move_str += "+"
			
		self.promotion_pending = False
		self.promotion_coords = None
		
		if hasattr(self, 'play_sound') and getattr(self, 'game_mode', '') != 'replay': 
			self.play_sound('promote')
		self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'

	def place_duck(self, pos, animated=True):
		"""Finalizes the turn by placing the duck and saving state."""
		if self.board[pos[0]][pos[1]] or pos == self.prev_duck_pos: return

		if hasattr(self, 'play_sound') and getattr(self, 'game_mode', '') != 'replay':
			self.play_sound('notify')

		coords = NotationHelper.get_notation_coords(pos[0], pos[1])
		log_entry = f"{self.current_move_str} @ {coords}"
		
		if self.turn == 'w':
			self.move_log.append(f"{self.turn_number}. {log_entry}")
		else:
			self.move_log.append(f"{self.turn_number}... {log_entry}")
			self.turn_number += 1

		self.duck_pos = pos
		self.phase, self.turn = 'move_piece', ('b' if self.turn == 'w' else 'w')
		
		self.save_snapshot()
		self.check_game_end_conditions()

		is_ai_next = (self.game_mode == 'white_ai' and self.turn == 'b') or \
					 (self.game_mode == 'black_ai' and self.turn == 'w')
		if is_ai_next and not self.game_over:
			self.waiting_for_ai = True
			self.ai_wait_start = pygame.time.get_ticks()
		else:
			self.waiting_for_ai = False

	def ai_turn(self):
		"""Automated logic for the AI player's moves."""
		if self.view_index != len(self.history) - 1 or self.game_over or not getattr(self, 'waiting_for_ai', False): return
		if pygame.time.get_ticks() - self.ai_wait_start < 400: return

		if self.phase == 'move_piece':
			move = self.ai.get_piece_move(self.board, self.turn, self.get_piece_legal_moves)
			if move:
				self.execute_move(move[0], move[1], animated=True)
			else:
				self.game_over = True
				self.winner = 'b' if self.turn == 'w' else 'w'
		elif self.phase == 'move_duck':
			target = self.ai.get_duck_move(self.board, self.duck_pos, self.prev_duck_pos)
			if target:
				self.place_duck(target, animated=True)