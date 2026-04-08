import gymnasium as gym
import numpy as np
from gymnasium import spaces
import torch as th
import pickle
import time
import os
import random
import uuid

from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.constants import KING, KNIGHT, BISHOP, PIECE_VALUES

class HeadlessEngine(GameLogicMixin):
	"""A lightweight version of the game strictly for fast RL training."""
	def __init__(self):
		self.game_mode = 'rl_training'
		self.reset_game_state()

class DuckChessEnvStage10(gym.Env):
	"""Stage 10 V3: Anti-Farming & Endgame Optimization."""
	def __init__(self, render_mode=None):
		super(DuckChessEnvStage10, self).__init__()
		self.action_space = spaces.Discrete(4096)
		self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
		self.render_mode = render_mode
		
		self.engine = HeadlessEngine()
		self.opponent_latest = None
		self.opponent_historical = None
		
		self.episode_counter = 0
		self.current_episode_actions = []
		
		self.learning_color = 'w'
		self.opponent_color = 'b'
		
		# Strategic Scaling Factors
		self.material_scale = 0.05
		self.loss_penalty_multiplier = 1.2
		self.castling_bonus = 0.15
		self.defense_bonus = 0.02
		self.duck_blocking_scale = 0.01
		self.step_penalty = -0.007
		
		self.mobility_scale = 0.003
		
		# Endgame specific parameters
		self.endgame_material_threshold = 5.0
		self.king_push_bonus = 0.05
		
		self.checker = RulesChecker()
		
		self.tactical_values = PIECE_VALUES.copy()
		self.tactical_values[KING] = 10000

	def set_opponents(self, latest_model_path, historical_model_path=None):
		"""Loads the latest model and optionally a historical model for the league."""
		from sb3_contrib import MaskablePPO
		
		if latest_model_path and os.path.exists(latest_model_path):
			try:
				self.opponent_latest = MaskablePPO.load(latest_model_path, device="cpu")
			except Exception as e:
				pass
				
		if historical_model_path and os.path.exists(historical_model_path):
			try:
				self.opponent_historical = MaskablePPO.load(historical_model_path, device="cpu")
			except Exception as e:
				pass

	def _calculate_mobility(self, color):
		"""Counts total reachable squares for all pieces of a color without check-safety overhead."""
		controlled_squares = 0
		board = self.engine.board
		for r in range(8):
			for c in range(8):
				p = board[r][c]
				if p and p.color == color:
					moves = self.engine.get_piece_legal_moves(r, c)
					controlled_squares += len(moves)
		return controlled_squares

	def _count_threats(self, color):
		"""Checks if the King is in check just ONCE."""
		if self.checker.is_in_check(color, self.engine.board, self.engine.duck_pos):
			return 1
		return 0

	def _find_king(self, color):
		"""Locates the coordinates of the king for a specific color."""
		board = self.engine.board
		for r in range(8):
			for c in range(8):
				p = board[r][c]
				if p and p.type == KING and p.color == color:
					return (r, c)
		return None

	def _center_distance(self, pos):
		"""Calculates the Chebyshev distance from the center of the board (3.5, 3.5)."""
		r, c = pos
		return max(abs(r - 3.5), abs(c - 3.5))

	def reset(self, seed=None, options=None):
		super().reset(seed=seed)
		self.engine.reset_game_state()
		self.current_episode_actions = []
		self.episode_counter += 1
		self.learning_color = np.random.choice(['w', 'b'])
		self.opponent_color = 'b' if self.learning_color == 'w' else 'w'
		
		if self.learning_color == 'b':
			self._play_opponent_turn()
			
		return self.get_observation(), {}

	def get_observation(self):
		return self.engine._get_obs()

	def action_masks(self):
		masks = self.engine.action_masks()
		if not np.any(masks):
			masks[0] = True
			return masks

		if getattr(self.engine, 'phase', '') == 'move_piece':
			forced_mask = np.zeros(4096, dtype=bool)
			found_king_capture = False
			board = self.engine.board
			
			for action in np.where(masks)[0]:
				_, end = self.engine._decode_move(action)
				target = board[end[0]][end[1]]
				if target and target.type == KING and target.color != self.engine.turn:
					forced_mask[action] = True
					found_king_capture = True
					
			if found_king_capture:
				return forced_mask
		return masks

	def _get_smart_opponent_mask(self, original_mask):
		"""Optimized to only simulate if King is moving or if in check."""
		smart_mask = original_mask.copy()
		if getattr(self.engine, 'phase', '') != 'move_piece':
			return smart_mask

		board = self.engine.board
		in_check = self.checker.is_in_check(self.opponent_color, board, self.engine.duck_pos)
		
		for action in np.where(smart_mask)[0]:
			start, end = self.engine._decode_move(action)
			piece = board[start[0]][start[1]]
			
			if in_check or (piece and piece.type == KING):
				target_piece = board[end[0]][end[1]]
				board[end[0]][end[1]] = piece
				board[start[0]][start[1]] = None
				is_attacked = self.checker.is_in_check(self.opponent_color, board, self.engine.duck_pos)
				board[start[0]][start[1]] = piece
				board[end[0]][end[1]] = target_piece
				
				if in_check and is_attacked:
					smart_mask[action] = False
				elif piece and piece.type == KING and is_attacked:
					smart_mask[action] = False

		return smart_mask if np.any(smart_mask) else original_mask

	def _get_opponent_action(self):
		"""League distribution with hardcoded tactical priorities."""
		current_mask = self.action_masks()
		smart_mask = self._get_smart_opponent_mask(current_mask)
		valid_actions = np.where(smart_mask)[0]
		
		if len(valid_actions) == 0: return 0

		if self.engine.phase == 'move_piece':
			for action in valid_actions:
				_, end = self.engine._decode_move(action)
				target = self.engine.board[end[0]][end[1]]
				if target and target.type == KING: return action

			if not self.checker.is_in_check(self.opponent_color, self.engine.board, self.engine.duck_pos):
				best_capture, max_gain = None, 0
				for action in valid_actions:
					start, end = self.engine._decode_move(action)
					att, tgt = self.engine.board[start[0]][start[1]], self.engine.board[end[0]][end[1]]
					if att and tgt:
						att_v = 0 if att.type == KING else self.tactical_values.get(att.type, 0)
						gain = self.tactical_values.get(tgt.type, 0) - att_v
						if gain > max_gain:
							max_gain, best_capture = gain, action
				if best_capture is not None: return best_capture

		rand_val = np.random.rand()
		if rand_val < 0.20: return np.random.choice(valid_actions)
		
		obs = self.get_observation()
		if 0.20 <= rand_val < 0.50 and self.opponent_historical:
			action, _ = self.opponent_historical.predict(obs, action_masks=smart_mask, deterministic=False)
			return action
		if rand_val >= 0.50 and self.opponent_latest:
			action, _ = self.opponent_latest.predict(obs, action_masks=smart_mask, deterministic=False)
			return action
			
		return np.random.choice(valid_actions)

	def step(self, action):
		try:
			if not np.any(self.action_masks()):
				return self.get_observation(), 0.0, True, False, {}

			threats_before = self._count_threats(self.learning_color)
			material_before_abs = self.engine.calculate_material_score(self.engine.board)
			
			mobility_before = 0
			opp_mob_before = 0
			opp_king_before = None
			
			if self.engine.phase == 'move_piece':
				mobility_before = self._calculate_mobility(self.learning_color)
				opp_king_before = self._find_king(self.opponent_color)
			elif self.engine.phase == 'move_duck':
				opp_mob_before = self._calculate_mobility(self.opponent_color)

			pos_bonus = 0
			if self.engine.phase == 'move_piece':
				start, end = self.engine._decode_move(action)
				p = self.engine.board[start[0]][start[1]]
				if p and p.type == KING and abs(start[1] - end[1]) == 2:
					pos_bonus = self.castling_bonus

			self._apply_action(action)
			self.current_episode_actions.append(int(action))

			rewards = {"material": 0, "pos": pos_bonus, "defense": 0, "blocking": 0, "mobility": 0, "endgame_push": 0}
			dynamic_step_penalty = self.step_penalty
			
			# Calculate current material advantage
			material_after_abs = self.engine.calculate_material_score(self.engine.board)
			my_adv = material_after_abs if self.learning_color == 'w' else -material_after_abs
			
			if self.engine.phase == 'move_piece':
				mobility_after = self._calculate_mobility(self.learning_color)
				rewards["mobility"] = (mobility_after - mobility_before) * self.mobility_scale
				
				threats_after = self._count_threats(self.learning_color)
				if threats_before > threats_after:
					rewards["defense"] = (threats_before - threats_after) * self.defense_bonus
					
				# Endgame Logic: Time Penalty Scaling & King Pushing
				if my_adv >= self.endgame_material_threshold:
					penalty_multiplier = 1.0 + (my_adv / 5.0)
					dynamic_step_penalty = self.step_penalty * penalty_multiplier
					
					opp_king_after = self._find_king(self.opponent_color)
					if opp_king_before and opp_king_after:
						dist_before = self._center_distance(opp_king_before)
						dist_after = self._center_distance(opp_king_after)
						if dist_after > dist_before:
							rewards["endgame_push"] = (dist_after - dist_before) * self.king_push_bonus
				
				if not self.engine.game_over:
					self._play_opponent_turn()
					
			elif self.engine.phase == 'move_duck':
				opp_mob_after = self._calculate_mobility(self.opponent_color)
				if opp_mob_before > opp_mob_after:
					rewards["blocking"] = (opp_mob_before - opp_mob_after) * self.duck_blocking_scale

			diff = (material_after_abs - material_before_abs) if self.learning_color == 'w' else (material_before_abs - material_after_abs)
			rewards["material"] = diff * self.material_scale * (self.loss_penalty_multiplier if diff < 0 else 1.0)

			total_reward = sum(rewards.values()) + dynamic_step_penalty
			terminated = getattr(self.engine, 'game_over', False)
			
			if terminated:
				total_reward += 1.0 if self.engine.winner == self.learning_color else (-1.0 if self.engine.winner == self.opponent_color else 0)
				if self.episode_counter % 1000 == 0: self._save_replay("periodic")

			return self.get_observation(), total_reward, terminated, False, {}

		except Exception as e:
			self._save_replay(f"CRASH_{type(e).__name__}")
			raise e

	def _apply_action(self, action):
		start, end = self.engine._decode_move(action)
		if self.engine.phase == 'move_piece': self.engine.execute_move(start, end, animated=False)
		else: self.engine.place_duck(end, animated=False)

	def _play_opponent_turn(self):
		"""Executes the opponent's logic until it is the learning agent's turn."""
		while self.engine.turn == self.opponent_color and not getattr(self.engine, 'game_over', False):
			if not np.any(self.action_masks()):
				self.engine.game_over = True
				self.engine.winner = 'draw'
				break
			opp_action = self._get_opponent_action()
			self._apply_action(opp_action)
			self.current_episode_actions.append(int(opp_action))

	def _save_replay(self, reason):
		"""Saves a pickle file of the game history. Uses UUID to prevent multiprocessing collisions."""
		save_dir = os.path.join("saved_replays", "stage 10")
		os.makedirs(save_dir, exist_ok=True)
		safe_reason = "".join([c for c in reason if c.isalpha() or c.isdigit() or c=='_'])[:30]
		unique_id = uuid.uuid4().hex[:6]
		filename = os.path.join(save_dir, f"{safe_reason}_ep{self.episode_counter}_{int(time.time())}_{unique_id}.pkl")
		try:
			with open(filename, 'wb') as f:
				pickle.dump({
					'action_history': self.current_episode_actions,
					'learning_color': self.learning_color,
					'opponent_color': self.opponent_color
				}, f)
		except: pass

	def render(self): pass
	def close(self): pass