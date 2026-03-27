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

	latest_path = os.path.join(MODEL_DIR, "duck_latest")
	latest_zip = latest_path + ".zip"

	# 3. Check for existing model to RESUME training safely with stability fixes
	if os.path.exists(latest_zip):
		print(f"\n[+] Found existing model at {latest_zip}. Resuming training with Stability Fixes!")
		model = MaskablePPO.load(
			latest_path, 
			env=env, 
			tensorboard_log=LOG_DIR,
			custom_objects={
				"learning_rate": 0.00007, # Lowered for stage 2 stability
				"target_kl": 0.015,       # Emergency brake to prevent Simplex crashes
				"n_steps": 1024,
				"batch_size": 64
			}
		)
	else:
		print("\n[+] No existing model found. Starting fresh training!")
		model = MaskablePPO(
			"CnnPolicy", 
			env, 
			policy_kwargs=policy_kwargs,
			verbose=1, 
			tensorboard_log=LOG_DIR,
			learning_rate=0.00007,
			target_kl=0.015,
			n_steps=1024,
			batch_size=64   
		)

	for i in range(TOTAL_ITERATIONS):
		print(f"\n--- Iteration {i+1} Start ---")
		
		# Added versioning to the log name to avoid overlapping lines in TensorBoard
		log_name = f"run_stage2_stable_iter_{i}"
		
		model.learn(
			total_timesteps=STEPS_PER_ITERATION,
			reset_num_timesteps=False,
			tb_log_name=log_name
		)

		# Save versions
		v_path = os.path.join(MODEL_DIR, f"duck_v{i}")
		model.save(v_path)
		model.save(latest_path)

		# Update Black Player
		if hasattr(env, 'set_attr'):
			env.set_attr("set_opponent", latest_zip)
		else:
			env.set_opponent(latest_zip)
			
		print(f"--- Iteration {i+1} Complete: Opponent Updated ---")

if __name__ == "__main__":
	train()