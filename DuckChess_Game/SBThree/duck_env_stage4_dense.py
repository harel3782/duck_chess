import gymnasium as gym
import numpy as np
from gymnasium import spaces
import torch as th
import pickle
import time
import os

from DuckChess_Game.Logic.logic import GameLogicMixin

class HeadlessEngine(GameLogicMixin):
	"""A lightweight version of the game strictly for fast RL training."""
	def __init__(self):
		self.game_mode = 'rl_training' 
		self.reset_game_state()

class DuckChessEnvStage4(gym.Env):
	"""Stage 4 Environment: Introduces Dense Rewards (Reward Shaping) for material capture."""
	def __init__(self, render_mode=None):
		super(DuckChessEnvStage4, self).__init__()
		self.action_space = spaces.Discrete(4096) 
		self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
		self.render_mode = render_mode
		
		self.engine = HeadlessEngine()
		self.opponent_model = None
		self.episode_counter = 0
		self.current_episode_actions = []
		
		self.learning_color = 'w'
		self.opponent_color = 'b'
		
		# Material reward scaling factor (e.g., taking a Queen (9) gives 9 * 0.05 = +0.45 reward)
		self.material_scale = 0.05

	def set_opponent(self, model_path):
		"""Loads a saved MaskablePPO model to act as the Self-Play opponent."""
		from sb3_contrib import MaskablePPO
		if os.path.exists(model_path):
			try:
				self.opponent_model = MaskablePPO.load(model_path, device="cpu")
			except Exception as e:
				print(f"Error loading opponent model: {e}")

	def reset(self, seed=None, options=None):
		"""Resets the env and randomly assigns the learning agent to White or Black."""
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
		"""REQUIRED for MaskablePPO: Returns valid move mask."""
		masks = self.engine.action_masks()
		if not np.any(masks):
			masks[0] = True
		return masks

	def _get_opponent_action(self):
		"""Phase 3/4: Self-Play logic."""
		current_mask = self.action_masks()
		if self.opponent_model is not None:
			obs = self.get_observation()
			with th.no_grad():
				action, _ = self.opponent_model.predict(obs, action_masks=current_mask, deterministic=False)
			return action
		
		valid_actions = np.where(current_mask)[0]
		return np.random.choice(valid_actions) if len(valid_actions) > 0 else 0

	def _save_replay(self, reason):
		"""Saves the game actions to a pickle file for later review."""
		os.makedirs("saved_replays", exist_ok=True)
		safe_reason = "".join([c for c in reason if c.isalpha() or c.isdigit() or c=='_'])[:30]
		filename = f"saved_replays/{safe_reason}_ep{self.episode_counter}_{int(time.time())}.pkl"
		try:
			with open(filename, 'wb') as f:
				pickle.dump({'action_history': self.current_episode_actions}, f)
			if "periodic" not in reason:
				print(f"\n[!!!] SAVE: {filename} (Reason: {reason})")
		except: pass

	def _apply_action(self, action):
		"""Decodes the action index and updates the engine."""
		start, end = self.engine._decode_move(action)
		if self.engine.phase == 'move_piece':
			self.engine.execute_move(start, end, animated=False)
		elif self.engine.phase == 'move_duck':
			self.engine.place_duck(end, animated=False)

	def _play_opponent_turn(self):
		"""Loops through the opponent's turn until it is the learning agent's turn."""
		while self.engine.turn == self.opponent_color and not getattr(self.engine, 'game_over', False):
			if not np.any(self.action_masks()):
				self._save_replay(f"{self.opponent_color}_stalemate")
				self.engine.game_over = True
				self.engine.winner = 'draw'
				break
				
			opp_action = self._get_opponent_action()
			self._apply_action(opp_action)
			self.current_episode_actions.append(int(opp_action))

	def step(self, action):
		"""Core training loop with Reward Shaping based on material advantage."""
		try:
			if not np.any(self.action_masks()):
				self._save_replay(f"{self.learning_color}_stalemate")
				return self.get_observation(), 0.0, True, False, {}

			# Capture old material score before learning agent moves
			old_material_score = self.engine.calculate_material_score(self.engine.board)

			# 1. Apply Learning Agent's move
			self._apply_action(action)
			self.current_episode_actions.append(int(action))

			# 2. Let the Opponent play their turn
			if not getattr(self.engine, 'game_over', False):
				self._play_opponent_turn()

			# Capture new material score after full turn cycle
			new_material_score = self.engine.calculate_material_score(self.engine.board)

			# Calculate material difference relative to learning agent's color
			# Score is Positive if White has advantage.
			if self.learning_color == 'w':
				material_diff = new_material_score - old_material_score
			else:
				material_diff = old_material_score - new_material_score

			# 3. Calculate Final Reward
			reward = material_diff * self.material_scale
			terminated = getattr(self.engine, 'game_over', False)
			
			if terminated:
				if self.engine.winner == self.learning_color: 
					reward += 1.0 # Big bonus for winning
				elif self.engine.winner == self.opponent_color: 
					reward -= 1.0 # Big penalty for losing
				else: 
					reward += 0.0

			# Periodic Saves
			if terminated and self.episode_counter % 50 == 0:
				self._save_replay("periodic_sample")

			return self.get_observation(), reward, terminated, False, {}

		except Exception as e:
			self._save_replay(f"CRASH_{type(e).__name__}")
			raise e

	def render(self): pass
	def close(self): pass