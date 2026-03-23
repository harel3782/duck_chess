import gymnasium as gym
import numpy as np
from gymnasium import spaces
import torch as th

class DuckChessEnv(gym.Env):
	def __init__(self, render_mode=None):
		super(DuckChessEnv, self).__init__()
		
		# Action Space: 8x8 (from) * 8x8 (to) * 8x8 (duck)
		# Adjust the size to match your engine's flattened representation
		self.action_space = spaces.Discrete(262144) 
		
		# Observation Space: 19 layers of 8x8 grids
		self.observation_space = spaces.Box(
			low=0.0, 
			high=1.0, 
			shape=(19, 8, 8), 
			dtype=np.float32
		)
		
		self.render_mode = render_mode
		self.opponent_model = None
		# Initialize your engine here
		# self.engine = DuckChessEngine() 

	def set_opponent(self, model_path):
		"""
		Loads a saved MaskablePPO model to act as the Black player.
		"""
		from sb3_contrib import MaskablePPO
		try:
			# Load model on CPU to avoid VRAM overhead during training
			self.opponent_model = MaskablePPO.load(model_path, device="cpu")
		except Exception as e:
			print(f"Error loading opponent model: {e}")

	def reset(self, seed=None, options=None):
		super().reset(seed=seed)
		# Reset internal engine state
		# self.engine.reset()
		
		observation = self.get_observation()
		return observation, {}

	def get_observation(self):
		"""
		Encodes the current board state into a (19, 8, 8) tensor.
		"""
		# Dummy observation - replace with actual engine state encoding
		return np.zeros((19, 8, 8), dtype=np.float32)

	def action_masks(self):
		"""
		Returns a legal move mask. Must be np.int8 for Gymnasium compatibility.
		"""
		# Replace with actual legal moves from engine
		mask = np.ones(self.action_space.n, dtype=np.int8)
		return mask

    def _get_black_action(self):
        current_mask = self.action_masks()
        
        if self.opponent_model is not None:
            obs = self.get_observation()
            # CRITICAL: Disable gradient calculation for the opponent player
            with th.no_grad():
                action, _ = self.opponent_model.predict(
                    obs, 
                    action_masks=current_mask, 
                    deterministic=False
                )
            return action

        return self.action_space.sample(mask=current_mask)

	def step(self, action):
		"""
		Core logic: White move -> Reward Check -> Black move -> Reward Check.
		"""
		# 1. White (the agent) makes a move
		# self.engine.make_move(action)
		
		reward = 0.0
		terminated = False
		truncated = False

		# 2. Check game status after White's move
		# if self.engine.is_checkmate():
		# 	reward = 1.0 # Win
		# 	terminated = True
		# elif self.engine.is_draw():
		# 	reward = -0.1 # Draw
		# 	terminated = True

		# 3. If game continues, Black makes a move
		if not terminated:
			black_action = self._get_black_action()
			# self.engine.make_move(black_action)
			
			# Check if White lost after Black's move
			# if self.engine.is_checkmate(): 
			# 	reward = -1.0 # Loss
			# 	terminated = True

		observation = self.get_observation()
		return observation, reward, terminated, truncated, {}

	def render(self):
		pass

	def close(self):
		pass