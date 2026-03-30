import pickle
import json
import copy
import pygame
import os
from DuckChess_Game.Logic.bitboard_manager import BitboardManager

class HistoryManagerMixin:
	"""Handles game state initialization, snapshots, and replays including special move data."""

	def clear_board(self):
		"""Removes all pieces from the board."""
		self.board = [[None] * 8 for _ in range(8)]
		self.duck_pos = (-1, -1)
		self.turn = 'w'
		self.move_log = []
		self.history = []
		if hasattr(self, 'bb_mgr'):
			self.bb_mgr = BitboardManager()

	def save_snapshot(self):
		"""Saves a single point in history including En Passant target."""
		self.history.append({
			'board': copy.deepcopy(self.board),
			'duck_pos': self.duck_pos,
			'prev_duck': getattr(self, 'prev_duck_pos', (-1, -1)),
			'en_passant_target': getattr(self, 'en_passant_target', None),
			'last_move': getattr(self, 'last_move_arrow', None),
			'captured': copy.deepcopy(getattr(self, 'captured', {'w': [], 'b': []})),
			'log': list(self.move_log)
		})
		self.view_index = len(self.history) - 1

	def reset_game_state(self):
		"""Completely resets the game environment to the initial setup."""
		self.duck_pos = (-1, -1)
		self.prev_duck_pos = (-1, -1)
		self.en_passant_target = None
		self.turn = 'w'
		self.phase = 'move_piece'
		self.selected_square = None
		self.valid_moves = []
		self.game_over = False
		self.winner = None
		self.half_move_clock = 0
		self.rep_history = {}
		
		# Reset save status and action tracker for new games
		self.game_saved = False
		self.replay_actions = []

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

	def load_replay_file(self, filepath):
		"""Loads a .pkl or .json replay file and reconstructs history."""
		if not os.path.exists(filepath): return
		
		try:
			if filepath.endswith('.json'):
				with open(filepath, 'r', encoding='utf-8') as f:
					game_data = json.load(f)
				actions = game_data.get('replay_actions', [])
				
				if not actions: return
				
				self.reset_game_state()
				self.game_mode, self.state = 'replay', 'game'
				
				# --- Extract player names for HUD ---
				players = game_data.get('players', {})
				self.replay_white_name = players.get('white', 'Unknown')
				self.replay_black_name = players.get('black', 'Unknown')
				
				for act in actions:
					if act['type'] == 'piece':
						self.execute_move(tuple(act['start']), tuple(act['end']), animated=False)
					elif act['type'] == 'duck':
						self.place_duck(tuple(act['pos']), animated=False)
					elif act['type'] == 'promote':
						self.promote_pawn(act['piece'])
						
			else:
				with open(filepath, 'rb') as f:
					game_data = pickle.load(f)
					
				actions = game_data.get('action_history', [])
				if not actions: return
				
				self.reset_game_state()
				self.game_mode, self.state = 'replay', 'game'
				self.replay_learning_color = game_data.get('learning_color', 'unknown')
				
				for act in actions:
					start, end = getattr(self, '_decode_move')(act)
					if self.phase == 'move_piece':
						self.execute_move(start, end, animated=False)
					elif self.phase == 'move_duck':
						self.place_duck(end, animated=False)
						
		except Exception as e:
			print(f"Failed to load replay: {e}")
			return

		self.view_index = len(self.history) - 1