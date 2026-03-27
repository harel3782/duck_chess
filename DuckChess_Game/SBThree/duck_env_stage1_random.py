import gymnasium as gym
import numpy as np
from gymnasium import spaces
import torch as th
import pickle
import time
import os

from DuckChess_Game.Logic.logic import GameLogicMixin

class HeadlessEngine(GameLogicMixin):
	"""A lightweight, Pygame-free version of the game strictly for extremely fast RL training."""
	def __init__(self):
		self.game_mode = 'rl_training' 
		self.reset_game_state()

class DuckChessEnv(gym.Env):
	def __init__(self, render_mode=None):
		super(DuckChessEnv, self).__init__()
		
		self.action_space = spaces.Discrete(4096) 
		self.observation_space = spaces.Box(
			low=0.0, 
			high=1.0, 
			shape=(19, 8, 8), 
			dtype=np.float32
		)
		
		self.render_mode = render_mode
		self.opponent_model = None
		self.engine = HeadlessEngine()
		
		self.current_episode_actions = []
		self.episode_counter = 0

	def set_opponent(self, model_path):
		"""Loads a saved MaskablePPO model to act as the Black player."""
		from sb3_contrib import MaskablePPO
		try:
			self.opponent_model = MaskablePPO.load(model_path, device="cpu")
		except Exception as e:
			print(f"Error loading opponent model: {e}")

	def reset(self, seed=None, options=None):
		"""Resets the environment for a new game and increments the episode counter."""
		super().reset(seed=seed)
		self.engine.reset_game_state()
		self.current_episode_actions = []
		self.episode_counter += 1
		return self.get_observation(), {}

	def get_observation(self):
		"""Calls our fast Bitboard observation encoder."""
		return self.engine._get_obs()

	def action_masks(self):
		"""Calls our fast Bitboard action masker, safely handling stalemates."""
		masks = self.engine.action_masks()
		if not np.any(masks):
			masks[0] = True
		return masks

	def _get_black_action(self):
		"""Generates a move for the opponent. CURRICULUM STAGE 1: RANDOM BOT."""
		current_mask = self.action_masks()
		
		if self.opponent_model is not None:
			obs = self.get_observation()
			with th.no_grad():
				action, _ = self.opponent_model.predict(
					obs, 
					action_masks=current_mask, 
					deterministic=False
				)
			return action

		valid_actions = np.where(current_mask)[0]
		if len(valid_actions) > 0:
			# Pure random choice for Stage 1
			return np.random.choice(valid_actions)
		return 0

	def _save_replay(self, reason):
		"""Saves the game log to a file for periodic review, crashes, or stalemates."""
		os.makedirs("saved_replays", exist_ok=True)
		safe_reason = "".join([c for c in reason if c.isalpha() or c.isdigit() or c=='_'])[:30]
		filename = f"saved_replays/{safe_reason}_ep{self.episode_counter}_{int(time.time())}.pkl"
		try:
			with open(filename, 'wb') as f:
				pickle.dump({'action_history': self.current_episode_actions}, f)
			
			if "periodic" in reason:
				print(f"\n[i] Sample Game Saved -> {filename}")
			else:
				print(f"\n[!!!] EMERGENCY SAVE: {filename} (Reason: {reason})")
		except Exception as e:
			print(f"Failed to save replay: {e}")

	def step(self, action):
		"""Core training loop wrapped in a global try-except to catch all crashes."""
		try:
			if not np.any(self.engine.action_masks()):
				self._save_replay("white_stalemate")
				return self.get_observation(), 0.0, True, False, {}

			self._apply_action(action)
			self.current_episode_actions.append(int(action))
			
			reward = 0.0
			terminated = getattr(self.engine, 'game_over', False)
			truncated = False

			if terminated:
				if self.engine.winner == 'w': reward = 1.0
				elif self.engine.winner == 'draw': reward = 0.0
				else: reward = -1.0
			else:
				while self.engine.turn == 'b' and not getattr(self.engine, 'game_over', False):
					if not np.any(self.engine.action_masks()):
						self._save_replay("black_stalemate")
						self.engine.game_over = True
						self.engine.winner = 'draw'
						break
						
					black_action = self._get_black_action()
					self._apply_action(black_action)
					self.current_episode_actions.append(int(black_action))
				
				terminated = getattr(self.engine, 'game_over', False)
				if terminated:
					if self.engine.winner == 'w': reward = 1.0
					elif self.engine.winner == 'draw': reward = 0.0
					else: reward = -1.0

			# --- PERIODIC SAVING ---
			if terminated and self.episode_counter % 50 == 0:
				self._save_replay("periodic_sample")

			observation = self.get_observation()
			return observation, reward, terminated, truncated, {}

		except Exception as e:
			self._save_replay(f"CRASH_{type(e).__name__}")
			raise e

	def _apply_action(self, action):
		"""Decodes the action index and updates the engine."""
		start, end = self.engine._decode_move(action)
		if self.engine.phase == 'move_piece':
			self.engine.execute_move(start, end, animated=False)
		elif self.engine.phase == 'move_duck':
			self.engine.place_duck(end, animated=False)

	def render(self):
		pass

	def close(self):
		pass