import os
import time
import torch as th
import torch.nn as nn
import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from DuckChess_Game.SBThree.duck_env_stage5_strategic import DuckChessEnvStage5

class DuckChessCNN(BaseFeaturesExtractor):
	"""Custom CNN for 8x8 board processing."""
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
TOTAL_ITERATIONS = 15 
STEPS_PER_ITERATION = 100000 
MODEL_DIR = "models/duck_ppo/"
LOG_DIR = "./tensorboard_logs/"

def train():
	os.makedirs(MODEL_DIR, exist_ok=True)

	# Initialize Stage 5 Environment (Strategic Duck)
	env = DuckChessEnvStage5() 

	policy_kwargs = dict(
		features_extractor_class=DuckChessCNN,
		features_extractor_kwargs=dict(features_dim=256),
	)

	# Load the stable v6 model from Stage 4 to build upon
	base_model_path = os.path.join(MODEL_DIR, "stage4_dense_v6.zip")
	latest_path = os.path.join(MODEL_DIR, "stage5_strategic_latest")
	latest_zip = latest_path + ".zip"

	if os.path.exists(base_model_path):
		print(f"\n[+] Found base model at {base_model_path}. Starting STAGE 5 (Strategic Duck)!")
		model = MaskablePPO.load(
			base_model_path, 
			env=env, 
			tensorboard_log=LOG_DIR,
			custom_objects={
				"learning_rate": 0.00001, # Kept low for stability
				"target_kl": 0.01,
				"ent_coef": 0.04,         # High enough to explore duck placements
				"max_grad_norm": 0.3,     # CRITICAL: Strict gradient clipping to prevent explosion
				"n_steps": 1024,
				"batch_size": 64,
				"stats_window_size": 100
			}
		)
		# Set initial opponent to the base model
		if hasattr(env, 'set_attr'):
			env.set_attr("set_opponent", base_model_path)
		else:
			env.set_opponent(base_model_path)
	else:
		print(f"\n[-] ERROR: Base model {base_model_path} not found. Please check filenames.")
		return

	# Start Stage 5 Iterations
	for i in range(TOTAL_ITERATIONS):
		print(f"\n--- Stage 5 (Strategic Duck) Iteration {i} Start ---")
		
		log_name = f"run_stage5_strategic_iter_{i}"
		
		model.learn(
			total_timesteps=STEPS_PER_ITERATION,
			reset_num_timesteps=False, 
			tb_log_name=log_name
		)

		v_path = os.path.join(MODEL_DIR, f"stage5_strategic_v{i}")
		model.save(v_path)
		model.save(latest_path)

		if hasattr(env, 'set_attr'):
			env.set_attr("set_opponent", latest_zip)
		else:
			env.set_opponent(latest_zip)
			
		print(f"--- Iteration {i} Complete: Opponent Updated ---")

if __name__ == "__main__":
	train()