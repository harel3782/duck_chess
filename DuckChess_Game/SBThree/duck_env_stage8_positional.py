import gymnasium as gym
import numpy as np
from gymnasium import spaces
import torch as th
import pickle
import time
import os

from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.constants import KING, KNIGHT, BISHOP, PIECE_VALUES

class HeadlessEngine(GameLogicMixin):
	"""A lightweight version of the game strictly for fast RL training."""
	def __init__(self):
		self.game_mode = 'rl_training'
		self.reset_game_state()

class DuckChessEnvStage8(gym.Env):
	"""Stage 8 Environment: Positional Mastery. Rewards castling, development, and penalizes hanging pieces."""
	def __init__(self, render_mode=None):
		super(DuckChessEnvStage8, self).__init__()
		self.action_space = spaces.Discrete(4096)
		self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
		self.render_mode = render_mode
		
		self.engine = HeadlessEngine()
		self.opponent_model = None
		self.episode_counter = 0
		self.current_episode_actions = []
		
		self.learning_color = 'w'
		self.opponent_color = 'b'
		
		# Strategic Scaling Factors
		self.material_scale = 0.05
		self.loss_penalty_multiplier = 1.5	# Losing a piece hurts 1.5x more than capturing
		self.castling_bonus = 0.2
		self.development_bonus = 0.05
		self.defense_bonus = 0.03
		self.duck_blocking_scale = 0.015	# Reward scale for reducing opponent mobility
		self.step_penalty = -0.005
		self.checker = RulesChecker()

	def set_opponent(self, model_path):
		"""Loads a saved MaskablePPO model to act as the opponent."""
		from sb3_contrib import MaskablePPO
		if os.path.exists(model_path):
			try:
				self.opponent_model = MaskablePPO.load(model_path, device="cpu")
			except Exception as e:
				print(f"Error loading opponent model: {e}")

	def _count_threats(self, color):
		threats = 0
		board = self.engine.board
		duck = self.engine.duck_pos
		for r in range(8):
			for c in range(8):
				p = board[r][c]
				if p and p.color == color:
					if self.checker.is_in_check(color, board, duck):
						threats += 1
		return threats

	def _calculate_mobility(self, color):
		"""Calculates the total number of legal moves available to a specific color."""
		mobility = 0
		for r in range(8):
			for c in range(8):
				p = self.engine.board[r][c]
				if p and p.color == color:
					moves = self.engine.get_piece_legal_moves(r, c)
					mobility += len(moves)
		return mobility

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
			forced_capture_mask = np.zeros(4096, dtype=bool)
			found_king_capture = False
			board = self.engine.board
			
			for action in np.where(masks)[0]:
				start, end = self.engine._decode_move(action)
				target_piece = board[end[0]][end[1]]
				if target_piece and target_piece.type == KING and target_piece.color != self.engine.turn:
					forced_capture_mask[action] = True
					found_king_capture = True
					
			if found_king_capture:
				return forced_capture_mask
		return masks

	def _get_opponent_action(self):
		"""Mixed logic: 30% Smart Greedy, 5% Random, 65% Loaded Model."""
		current_mask = self.action_masks()
		valid_actions = np.where(current_mask)[0]
		
		if len(valid_actions) == 0:
			return 0
			
		rand_val = np.random.rand()
		
		# 30% chance: Play Smart Greedy (Only eat if target value >= attacker value)
		if rand_val < 0.30 and self.engine.phase == 'move_piece':
			best_capture_action = None
			max_capture_value = -1
			
			for action_idx in valid_actions:
				start, end = self.engine._decode_move(action_idx)
				attacker = self.engine.board[start[0]][start[1]]
				target = self.engine.board[end[0]][end[1]]
				
				if target is not None and attacker is not None:
					target_val = PIECE_VALUES.get(target.type, 0)
					attacker_val = PIECE_VALUES.get(attacker.type, 0)
					
					if target_val >= attacker_val and target_val > max_capture_value:
						max_capture_value = target_val
						best_capture_action = action_idx
						
			if best_capture_action is not None:
				return best_capture_action
			return np.random.choice(valid_actions)
			
		# 5% chance: Play completely Random
		elif rand_val < 0.35:
			return np.random.choice(valid_actions)
			
		# 65% chance: Play using the currently loaded historical model
		else:
			if self.opponent_model is not None:
				obs = self.get_observation()
				with th.no_grad():
					action, _ = self.opponent_model.predict(obs, action_masks=current_mask, deterministic=False)
				return action
			return np.random.choice(valid_actions)

	def _save_replay(self, reason):
		save_dir = os.path.join("saved_replays", "stage 8")
		os.makedirs(save_dir, exist_ok=True)
		safe_reason = "".join([c for c in reason if c.isalpha() or c.isdigit() or c=='_'])[:30]
		filename = os.path.join(save_dir, f"{safe_reason}_ep{self.episode_counter}_{int(time.time())}.pkl")
		try:
			with open(filename, 'wb') as f:
				pickle.dump({
					'action_history': self.current_episode_actions,
					'learning_color': self.learning_color,
					'opponent_color': self.opponent_color
				}, f)
		except: pass

	def _apply_action(self, action):
		start, end = self.engine._decode_move(action)
		if self.engine.phase == 'move_piece':
			self.engine.execute_move(start, end, animated=False)
		elif self.engine.phase == 'move_duck':
			self.engine.place_duck(end, animated=False)

	def _play_opponent_turn(self):
		while self.engine.turn == self.opponent_color and not getattr(self.engine, 'game_over', False):
			if not np.any(self.action_masks()):
				self.engine.game_over = True
				self.engine.winner = 'draw'
				break
			opp_action = self._get_opponent_action()
			self._apply_action(opp_action)
			self.current_episode_actions.append(int(opp_action))

	def step(self, action):
		try:
			if not np.any(self.action_masks()):
				return self.get_observation(), 0.0, True, False, {}

			threats_before = self._count_threats(self.learning_color)
			old_material = self.engine.calculate_material_score(self.engine.board)

			# Track opponent mobility BEFORE the duck is placed
			opp_mobility_before = 0
			if self.engine.phase == 'move_duck':
				opp_mobility_before = self._calculate_mobility(self.opponent_color)

			# Check positional moves before applying the action
			pos_bonus = 0
			if self.engine.phase == 'move_piece':
				start, end = self.engine._decode_move(action)
				piece = self.engine.board[start[0]][start[1]]
				if piece is not None:
					# Reward Castling (King moves 2 squares horizontally)
					if piece.type == KING and abs(start[1] - end[1]) == 2:
						pos_bonus += self.castling_bonus
						
					# Reward Development (Minor pieces leaving the back rank)
					elif piece.type in [KNIGHT, BISHOP]:
						back_rank = 7 if self.learning_color == 'w' else 0
						if start[0] == back_rank and end[0] != back_rank:
							pos_bonus += self.development_bonus

			self._apply_action(action)
			self.current_episode_actions.append(int(action))

			duck_bonus = 0
			blocking_bonus = 0

			if self.engine.phase == 'move_piece':
				threats_after = self._count_threats(self.learning_color)
				if threats_before > threats_after:
					duck_bonus = (threats_before - threats_after) * self.defense_bonus

				# Calculate mobility reduction caused by the new duck placement
				opp_mobility_after = self._calculate_mobility(self.opponent_color)
				if opp_mobility_before > opp_mobility_after:
					blocking_bonus = (opp_mobility_before - opp_mobility_after) * self.duck_blocking_scale
				
				if not getattr(self.engine, 'game_over', False):
					self._play_opponent_turn()

			new_material = self.engine.calculate_material_score(self.engine.board)
			
			# Asymmetric material calculation
			if self.learning_color == 'w':
				material_diff = new_material - old_material
			else:
				material_diff = old_material - new_material

			if material_diff < 0:
				material_reward = material_diff * self.material_scale * self.loss_penalty_multiplier
			else:
				material_reward = material_diff * self.material_scale

			# Integrate the new blocking_bonus into the final reward step
			reward = material_reward + duck_bonus + pos_bonus + blocking_bonus + self.step_penalty
			terminated = getattr(self.engine, 'game_over', False)
			
			if terminated:
				if self.engine.winner == self.learning_color:
					reward += 1.0
				elif self.engine.winner == self.opponent_color:
					reward -= 1.0

			if terminated and self.episode_counter % 1000 == 0:
				self._save_replay("periodic_sample")

			return self.get_observation(), reward, terminated, False, {}

		except Exception as e:
			self._save_replay(f"CRASH_{type(e).__name__}")
			raise e

	def render(self): pass
	def close(self): pass