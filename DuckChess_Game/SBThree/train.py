import os
import time
import torch as th
import torch.nn as nn
import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from DuckChess_Game.SBThree.duck_env_stage4_dense import DuckChessEnvStage4

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
TOTAL_ITERATIONS = 15 # Extended for Stage 4
STEPS_PER_ITERATION = 100000 
MODEL_DIR = "models/duck_ppo/"
LOG_DIR = "./tensorboard_logs/"

def train():
	os.makedirs(MODEL_DIR, exist_ok=True)

	# Initialize Stage 4 Environment (Dense Rewards)
	env = DuckChessEnvStage4() 

	policy_kwargs = dict(
		features_extractor_class=DuckChessCNN,
		features_extractor_kwargs=dict(features_dim=256),
	)

	base_model_path = os.path.join(MODEL_DIR, "stage3_selfplay_v4.zip")
	latest_path = os.path.join(MODEL_DIR, "stage4_dense_latest")
	latest_zip = latest_path + ".zip"

	if os.path.exists(base_model_path):
		print(f"\n[+] Found base model at {base_model_path}. Starting STAGE 4 (Dense Rewards)!")
		model = MaskablePPO.load(
			base_model_path, 
			env=env, 
			tensorboard_log=LOG_DIR,
			custom_objects={
				"learning_rate": 0.00001, # Lowered for stability
				"target_kl": 0.01,
				"ent_coef": 0.05,         # Increased significantly to force exploration
				"max_grad_norm": 0.3,     # Strict gradient clipping
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

	# Start Stage 4 Iterations
	for i in range(TOTAL_ITERATIONS):
		print(f"\n--- Stage 4 (Dense Rewards) Iteration {i} Start ---")
		
		log_name = f"run_stage4_dense_iter_{i}"
		
		model.learn(
			total_timesteps=STEPS_PER_ITERATION,
			reset_num_timesteps=False, 
			tb_log_name=log_name
		)

		v_path = os.path.join(MODEL_DIR, f"stage4_dense_v{i}")
		model.save(v_path)
		model.save(latest_path)

		if hasattr(env, 'set_attr'):
			env.set_attr("set_opponent", latest_zip)
		else:
			env.set_opponent(latest_zip)
			
		print(f"--- Iteration {i} Complete: Opponent Updated ---")

if __name__ == "__main__":
	train()