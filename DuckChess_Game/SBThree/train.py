import os
import torch as th
import torch.nn as nn
import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from DuckChess_Game.SBThree.duck_env import DuckChessEnv

class DuckChessCNN(BaseFeaturesExtractor):
	"""
	Custom CNN for 8x8 board processing.
	Tailored for 19 layers of input.
	"""
	def __init__(self, observation_space, features_dim=256):
		super().__init__(observation_space, features_dim)
		n_input_channels = observation_space.shape[0]
		
		self.cnn = nn.Sequential(
			nn.Conv2d(n_input_channels, 32, kernel_size=3, stride=1, padding=1),
			nn.ReLU(),
			nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
			nn.ReLU(),
			nn.Flatten(),
		)

		with th.no_grad():
			sample_input = th.as_tensor(observation_space.sample()[None]).float()
			n_flatten = self.cnn(sample_input).shape[1]

		self.linear = nn.Sequential(
			nn.Linear(n_flatten, features_dim),
			nn.ReLU()
		)

	def forward(self, observations):
		return self.linear(self.cnn(observations))

# Global Constants
TOTAL_ITERATIONS = 10
STEPS_PER_ITERATION = 100000 
MODEL_DIR = "models/duck_ppo/"
LOG_DIR = "./tensorboard_logs/"

def train():
	os.makedirs(MODEL_DIR, exist_ok=True)

	# 1. Initialize Environment
	env = DuckChessEnv() 

	# 2. Policy Configuration
	policy_kwargs = dict(
		features_extractor_class=DuckChessCNN,
		features_extractor_kwargs=dict(features_dim=256),
	)

	# 3. Initialize Model with optimized Batch Size for CPU
	# Reducing n_steps and batch_size improves FPS on CPU
	model = MaskablePPO(
		"CnnPolicy", 
		env, 
		policy_kwargs=policy_kwargs,
		verbose=1, 
		tensorboard_log=LOG_DIR,
		learning_rate=0.0002,
		n_steps=1024,          # Reduced from 2048 to speed up rollout phase
		batch_size=64          # Smaller batches process faster on CPU
	)

	for i in range(TOTAL_ITERATIONS):
		print(f"\n--- Iteration {i+1} Start ---")
		
		model.learn(
			total_timesteps=STEPS_PER_ITERATION,
			reset_num_timesteps=False,
			tb_log_name=f"run_iter_{i}"
		)

		# Save versions
		v_path = os.path.join(MODEL_DIR, f"duck_v{i}")
		latest_path = os.path.join(MODEL_DIR, "duck_latest")
		model.save(v_path)
		model.save(latest_path)

		# Update Black Player
		opponent_zip = latest_path + ".zip"
		if hasattr(env, 'set_attr'):
			env.set_attr("set_opponent", opponent_zip)
		else:
			env.set_opponent(opponent_zip)
			
		print(f"--- Iteration {i+1} Complete: Opponent Updated ---")

if __name__ == "__main__":
	train()