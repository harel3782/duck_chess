import pygame
import pickle
import copy
from DuckChess_Game.UI.settings import *
from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.notation_helper import NotationHelper
from DuckChess_Game.Logic.move_executor import MoveExecutor

class StateManagerMixin:
	"""Handles high-level turn flow, AI execution, game state transitions, and replays."""

	def calculate_material_score(self, board_state):
		"""Calculates material balance using PIECE_VALUES from constants."""
		score = 0
		for r in range(8):
			for c in range(8):
				p = board_state[r][c]
				if p:
					val = PIECE_VALUES.get(p.type, 0)
					score += val if p.color == 'w' else -val
		return score

	def clear_board(self):
		"""Removes all pieces from the board."""
		self.board = [[None] * 8 for _ in range(8)]
		self.duck_pos = (-1, -1)
		self.turn = 'w'
		self.move_log = []
		self.history = []

	def save_snapshot(self):
		"""Saves a single point in history."""
		self.history.append({
			'board': copy.deepcopy(self.board),
			'duck_pos': self.duck_pos,
			'prev_duck': getattr(self, 'prev_duck_pos', (-1, -1)),
			'last_move': getattr(self, 'last_move_arrow', None),
			'captured': copy.deepcopy(getattr(self, 'captured', {'w': [], 'b': []})),
			'log': list(self.move_log)
		})
		self.view_index = len(self.history) - 1

	def reset_game_state(self):
		"""Completely resets the game environment."""
		self.duck_pos = (-1, -1)
		self.prev_duck_pos = (-1, -1)
		self.turn = 'w'
		self.phase = 'move_piece'
		self.selected_square = None
		self.valid_moves = []
		self.game_over = False
		self.winner = None
		self.en_passant_target = None
		self.half_move_clock = 0
		self.rep_history = {}

		self.move_log = []
		self.last_move_arrow = None
		self.turn_number = 1
		self.current_move_str = ""
		self.history = []
		self.view_index = -1

		self.captured = {'w': [], 'b': []}
		self.promotion_pending = False
		self.target_eval_score = 0
		self.current_eval_score = 0.0

		self.board = [[None] * 8 for _ in range(8)]
		self.init_board()

		if getattr(self, 'game_mode', None) == 'black_ai':
			self.waiting_for_ai = True
			self.ai_wait_start = pygame.time.get_ticks()
		else:
			self.waiting_for_ai = False

		self.save_snapshot()

	def execute_move(self, start, end, animated=True):
		"""Executes a piece move, plays sounds, checks for promotion, and transitions phases."""
		p = self.board[start[0]][start[1]]
		
		# Build notation and check for capture
		move_str = p.type if p.type != PAWN else ""
		is_capture = self.board[end[0]][end[1]] is not None
		if is_capture: move_str += "x"
		move_str += NotationHelper.get_notation_coords(end[0], end[1])
		self.current_move_str = move_str

		# Determine the correct sound effect
		is_castle = (p.type == KING and abs(start[1] - end[1]) == 2)
		sound_to_play = 'capture' if is_capture else ('castle' if is_castle else 'move')

		if animated and hasattr(self, 'animate_move_visual'):
			self.animate_move_visual(start, end, p, is_duck=False)

		executor = MoveExecutor()
		captured = executor.execute_piece_move(self.board, start, end)

		# Play the sound
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
				is_ai_turn = (getattr(self, 'game_mode', '') == 'rl_training') or \
							 (getattr(self, 'game_mode', '') == 'white_ai' and self.turn == 'b') or \
							 (getattr(self, 'game_mode', '') == 'black_ai' and self.turn == 'w')
				
				if is_ai_turn:
					p.type = QUEEN
					self.current_move_str += "=Q"
					if hasattr(self, 'play_sound'): self.play_sound('promote')
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
		
		if hasattr(self, 'play_sound'): self.play_sound('promote')
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

	def load_replay_file(self, filepath):
		"""Loads a .pkl replay file and reconstructs history turn-by-turn."""
		try:
			with open(filepath, 'rb') as f:
				game_data = pickle.load(f)
		except Exception as e:
			print(f"Failed to load replay: {e}")
			return

		actions = game_data.get('action_history', [])
		if not actions: return

		self.reset_game_state()
		self.game_mode, self.state = 'replay', 'game'

		for act in actions:
			(sr, sc), (er, ec) = getattr(self, '_decode_move')(act)
			if self.phase == 'move_piece':
				self.execute_move((sr, sc), (er, ec), animated=False)
			elif self.phase == 'move_duck':
				self.place_duck((er, ec), animated=False)

		self.view_index = len(self.history) - 1

	def check_game_end_conditions(self):
		"""Validates terminal states: 50-move rule and stalemate."""
		if self.game_over: return
		if hasattr(self, 'half_move_clock') and self.half_move_clock >= 100:
			self.game_over, self.winner = True, 'draw'; return

		has_moves = False
		for r in range(8):
			for c in range(8):
				p = self.board[r][c]
				if p and p.color == self.turn:
					if self.get_piece_legal_moves(r, c):
						has_moves = True; break
			if has_moves: break
		
		if not has_moves:
			self.game_over = True
			self.winner = 'b' if self.turn == 'w' else 'w'
			if hasattr(self, 'play_sound'): self.play_sound('game_over')