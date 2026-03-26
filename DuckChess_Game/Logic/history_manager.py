import pickle
import copy
import pygame

class HistoryManagerMixin:
	"""Handles game state initialization, snapshots, and replays."""

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