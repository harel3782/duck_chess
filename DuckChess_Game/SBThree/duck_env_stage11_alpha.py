import gymnasium as gym
import numpy as np
from gymnasium import spaces
import time
import os
import random
import pickle

from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.constants import KING, PIECE_VALUES

class HeadlessEngine(GameLogicMixin):
	"""Lightweight engine for RL."""
	def __init__(self):
		self.game_mode = 'rl_training'
		self.reset_game_state()

class DuckChessEnvStage11(gym.Env):
	"""Stage 11: True Sparse Rewards & Alpha-Beta Punisher. Chief Worker architecture."""
	def __init__(self, render_mode=None, env_index=0):
		super(DuckChessEnvStage11, self).__init__()
		self.env_index = env_index # Core ID (0 is Chief Worker)
		self.action_space = spaces.Discrete(4096)
		self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
		
		self.engine = HeadlessEngine()
		self.opponent_latest = None
		self.opponent_historical = None
		
		self.episode_counter = 0
		self.current_episode_actions = []
		self.learning_color = 'w'
		self.opponent_color = 'b'
		
		self.checker = RulesChecker()

	def set_opponents(self, latest_path, historical_path=None):
		from sb3_contrib import MaskablePPO
		if latest_path and os.path.exists(latest_path):
			try: self.opponent_latest = MaskablePPO.load(latest_path, device="cpu")
			except: pass
		if historical_path and os.path.exists(historical_path):
			try: self.opponent_historical = MaskablePPO.load(historical_path, device="cpu")
			except: pass

	def _get_alpha_beta_move(self):
		"""Depth 1: Greedy tactical execution."""
		best_action = None
		max_val = -float('inf')
		
		masks = self.action_masks()
		valid_actions = np.where(masks)[0]
		
		if self.engine.phase == 'move_piece':
			for action in valid_actions:
				_, end = self.engine._decode_move(action)
				target = self.engine.board[end[0]][end[1]]
				if target and target.type == KING: return action

			for action in valid_actions:
				start, end = self.engine._decode_move(action)
				piece = self.engine.board[start[0]][start[1]]
				target = self.engine.board[end[0]][end[1]]
				
				self.engine.board[end[0]][end[1]] = piece
				self.engine.board[start[0]][start[1]] = None
				
				score = self.engine.calculate_material_score(self.engine.board)
				val = score if self.opponent_color == 'w' else -score
				
				self.engine.board[start[0]][start[1]] = piece
				self.engine.board[end[0]][end[1]] = target
				
				if val > max_val:
					max_val, best_action = val, action
					
		return best_action if best_action is not None else np.random.choice(valid_actions)

	def _get_opponent_action(self):
		"""30% Alpha-Beta, 70% RL League."""
		rand = np.random.rand()
		if rand < 0.30:
			return self._get_alpha_beta_move()
		
		current_mask = self.action_masks()
		valid_actions = np.where(current_mask)[0]
		if len(valid_actions) == 0: return 0

		obs = self.get_observation()
		if rand < 0.65 and self.opponent_historical:
			action, _ = self.opponent_historical.predict(obs, action_masks=current_mask, deterministic=False)
			return action
		if self.opponent_latest:
			action, _ = self.opponent_latest.predict(obs, action_masks=current_mask, deterministic=False)
			return action
		return np.random.choice(valid_actions)

	def step(self, action):
		if not np.any(self.action_masks()):
			return self.get_observation(), 0.0, True, False, {}

		self._apply_action(action)
		self.current_episode_actions.append(int(action))

		if self.engine.phase == 'move_piece' and not self.engine.game_over:
			self._play_opponent_turn()

		# STRICT SPARSE REWARDS: Only reward at the end of the game
		total_reward = 0.0
		terminated = getattr(self.engine, 'game_over', False)
		
		if terminated:
			if self.engine.winner == self.learning_color:
				total_reward = 1.0
			elif self.engine.winner == self.opponent_color:
				total_reward = -1.0
			else:
				total_reward = 0.0
				
			# ONLY Chief Worker (env_index 0) is allowed to save replays
			if self.env_index == 0 and self.episode_counter % 1000 == 0: 
				self._save_replay()

		return self.get_observation(), total_reward, terminated, False, {}

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

	def get_observation(self): return self.engine._get_obs()
	def action_masks(self): return self.engine.action_masks()
	
	def _apply_action(self, action):
		start, end = self.engine._decode_move(action)
		if self.engine.phase == 'move_piece': self.engine.execute_move(start, end, animated=False)
		else: self.engine.place_duck(end, animated=False)

	def _play_opponent_turn(self):
		while self.engine.turn == self.opponent_color and not getattr(self.engine, 'game_over', False):
			if not np.any(self.action_masks()):
				self.engine.game_over, self.engine.winner = True, 'draw'
				break
			opp_action = self._get_opponent_action()
			self._apply_action(opp_action)
			# CRITICAL FIX: Save opponent action to log for UI sync
			self.current_episode_actions.append(int(opp_action))

	def _save_replay(self):
		"""Saves log using PID to ensure absolute uniqueness."""
		path = os.path.join("saved_replays", "stage 11")
		os.makedirs(path, exist_ok=True)
		worker_pid = os.getpid()
		fname = os.path.join(path, f"sparse_ep{self.episode_counter}_PID{worker_pid}_{int(time.time())}.pkl")
		with open(fname, 'wb') as f:
			pickle.dump({
				'action_history': self.current_episode_actions, 
				'learning_color': self.learning_color
			}, f)

	def render(self): pass
	def close(self): pass