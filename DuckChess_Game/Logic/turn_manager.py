import pygame
from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.notation_helper import NotationHelper
from DuckChess_Game.Logic.move_executor import MoveExecutor
from DuckChess_Game.UI.settings import AI_MOVE_DELAY

class TurnManagerMixin:
	"""Handles piece movement, duck placement, and AI turns with proper delays."""

	def execute_move(self, start, end, animated=True):
		"""Executes a piece move, handles promotion checks and transitions [cite: 29-30]."""
		p = self.board[start[0]][start[1]]
		if not p: return

		move_str = p.type if p.type != PAWN else ""
		is_capture = self.board[end[0]][end[1]] is not None
		if is_capture: move_str += "x"
		move_str += NotationHelper.get_notation_coords(end[0], end[1])
		self.current_move_str = move_str

		if animated and hasattr(self, 'animate_move_visual'):
			self.animate_move_visual(start, end, p, is_duck=False)

		executor = MoveExecutor()
		captured = executor.execute_piece_move(self.board, start, end)

		if hasattr(self, 'play_sound') and getattr(self, 'game_mode', '') != 'replay':
			self.play_sound('capture' if is_capture else 'move')

		if captured and captured.type == KING:
			self.game_over = True
			self.winner = self.turn
			self.save_snapshot()
		else:
			promote_rank = 0 if p.color == 'w' else 7
			if p.type == PAWN and end[0] == promote_rank:
				self._handle_promotion(p, end)
			else:
				self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'

	def _handle_promotion(self, pawn, pos):
		"""Internal helper for pawn promotion logic."""
		game_mode = getattr(self, 'game_mode', '')
		is_auto = game_mode in ('rl_training', 'replay') or \
				 (game_mode == 'white_ai' and self.turn == 'b') or \
				 (game_mode == 'black_ai' and self.turn == 'w')
		
		if is_auto:
			pawn.type = QUEEN
			self.current_move_str += "=Q"
			self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'
		else:
			self.promotion_pending = True
			self.promotion_coords = pos

	def promote_pawn(self, type_char):
		"""Called by the UI when the player selects a promotion piece[cite: 31]."""
		if not getattr(self, 'promotion_coords', None): return
		
		r, c = self.promotion_coords
		self.board[r][c].type = type_char
		self.current_move_str += f"={type_char}"
		
		if hasattr(self, 'is_in_check') and self.is_in_check('b' if self.turn == 'w' else 'w'):
			if "+" not in self.current_move_str: self.current_move_str += "+"
			
		self.promotion_pending = False
		self.promotion_coords = None
		self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'

	def place_duck(self, pos, animated=True):
		"""Finalizes the turn by placing the duck and switching turns [cite: 31-32]."""
		if self.board[pos[0]][pos[1]] or pos == self.prev_duck_pos: return

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

	def ai_turn(self):
		"""Automated logic for the AI with the updated delay check."""
		if self.view_index != len(self.history) - 1 or self.game_over or not getattr(self, 'waiting_for_ai', False): return
		
		# Now uses the AI_MOVE_DELAY from settings.py
		if pygame.time.get_ticks() - self.ai_wait_start < AI_MOVE_DELAY: return

		if self.phase == 'move_piece':
			move = self.ai.get_piece_move(self.board, self.turn, self.get_piece_legal_moves)
			if move: self.execute_move(move[0], move[1], animated=True)
			else: self.game_over, self.winner = True, ('b' if self.turn == 'w' else 'w')
		elif self.phase == 'move_duck':
			target = self.ai.get_duck_move(self.board, self.duck_pos, self.prev_duck_pos)
			if target: self.place_duck(target, animated=True)