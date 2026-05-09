import gymnasium as gym
import numpy as np
from gymnasium import spaces
import time
import os
import random
import pickle
import uuid

from DuckChess_Game.Logic.logic import GameLogicMixin

class HeadlessEngine(GameLogicMixin):
	"""Minimalist engine for pure RL throughput."""
	def __init__(self):
		self.game_mode = 'rl_training'
		self.reset_game_state()

class DuckChessEnvStage12(gym.Env):
	"""Stage 12: Pure Self-Play. Sparse terminal rewards. Automatic retroactive credit assignment via PPO gamma."""
	def __init__(self, render_mode=None, env_index=0):
		super(DuckChessEnvStage12, self).__init__()
		self.env_index = env_index
		self.action_space = spaces.Discrete(4096)
		self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
		
		self.engine = HeadlessEngine()
		self.opponent_latest = None
		self.opponent_historical = None
		
		self.episode_counter = 0
		self.current_episode_actions = []
		self.learning_color = 'w'
		self.opponent_color = 'b'

	def set_opponents(self, latest_path, historical_path=None):
		"""Loads dynamic league opponents."""
		from sb3_contrib import MaskablePPO
		if latest_path and os.path.exists(latest_path):
			try: self.opponent_latest = MaskablePPO.load(latest_path, device="cpu")
			except: pass
		if historical_path and os.path.exists(historical_path):
			try: self.opponent_historical = MaskablePPO.load(historical_path, device="cpu")
			except: pass

	def _get_opponent_action(self):
		"""50% Latest Model, 50% Historical Model. Zero greedy/random logic."""
		current_mask = self.action_masks()
		valid_actions = np.where(current_mask)[0]
		if len(valid_actions) == 0: return 0

		rand = np.random.rand()
		obs = self.get_observation()
		
		if rand < 0.50 and self.opponent_historical:
			action, _ = self.opponent_historical.predict(obs, action_masks=current_mask, deterministic=False)
			return action
		if self.opponent_latest:
			action, _ = self.opponent_latest.predict(obs, action_masks=current_mask, deterministic=False)
			return action
			
		return np.random.choice(valid_actions)

	def step(self, action):
		"""Executes environment step. Returns zero intermediate reward."""
		if not np.any(self.action_masks()):
			return self.get_observation(), 0.0, True, False, {}

		self._apply_action(action)
		self.current_episode_actions.append(int(action))

		if self.engine.phase == 'move_piece' and not self.engine.game_over:
			self._play_opponent_turn()

		total_reward = 0.0
		terminated = getattr(self.engine, 'game_over', False)
		
		if terminated:
			# Terminal state: Assign rigid outcomes.
			# PPO uses Value Network to retroactively credit intermediate steps.
			if self.engine.winner == self.learning_color:
				total_reward = 1.0
			elif self.engine.winner == self.opponent_color:
				total_reward = -1.0
			else:
				total_reward = 0.1
				
			if self.env_index == 0 and self.episode_counter % 1000 == 0: 
				self._save_replay()

		return self.get_observation(), total_reward, terminated, False, {}

	def reset(self, seed=None, options=None):
		"""Resets state and randomizes learning color."""
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
		"""Opponent simulation loop."""
		while self.engine.turn == self.opponent_color and not getattr(self.engine, 'game_over', False):
			if not np.any(self.action_masks()):
				self.engine.game_over, self.engine.winner = True, 'draw'
				break
			opp_action = self._get_opponent_action()
			self._apply_action(opp_action)
			self.current_episode_actions.append(int(opp_action))

	def _save_replay(self):
		"""Process-safe replay dumping."""
		path = os.path.join("saved_replays", "stage 12")
		os.makedirs(path, exist_ok=True)
		worker_pid = os.getpid()
		unique_id = uuid.uuid4().hex[:6]
		fname = os.path.join(path, f"final_ep{self.episode_counter}_{unique_id}_PID{worker_pid}_{int(time.time())}.pkl")
		with open(fname, 'wb') as f:
			pickle.dump({
				'action_history': self.current_episode_actions, 
				'learning_color': self.learning_color
			}, f)

	def render(self): pass
	def close(self): pass