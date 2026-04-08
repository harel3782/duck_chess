import os
import glob
import random
import torch
from stable_baselines3 import PPO
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv

# Disable PyTorch strict validation to prevent float32 Simplex() crashes
torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage10_league import DuckChessEnvStage10

class LeagueCallback(BaseCallback):
	"""Manages the League: updates latest model and picks random historical opponent for all parallel envs."""
	def __init__(self, update_freq=50000, verbose=0):
		super().__init__(verbose)
		self.update_freq = update_freq
		self.models_dir = os.path.join("models", "duck_ppo")

	def _on_step(self) -> bool:
		if self.num_timesteps % self.update_freq == 0:
			stage10_dir = os.path.join(self.models_dir, "stage 10")
			os.makedirs(stage10_dir, exist_ok=True)
			
			current_path = os.path.join(stage10_dir, f"stage10_league_v{self.num_timesteps // self.update_freq}.zip")
			self.model.save(current_path)
			
			all_models = glob.glob(os.path.join(self.models_dir, "stage *", "*.zip"))
			historical_path = None
			if all_models:
				valid_models = [m for m in all_models if "latest" not in m and m != current_path]
				if valid_models: 
					historical_path = random.choice(valid_models)
			
			self.training_env.env_method("set_opponents", current_path, historical_path)
			
			if self.verbose > 0:
				hist_name = os.path.basename(historical_path) if historical_path else "None"
				print(f"[{self.num_timesteps}] League Updated | Latest: {os.path.basename(current_path)} | Hist: {hist_name}")
		return True

def get_latest_model(model_dir, prefix):
	models = glob.glob(os.path.join(model_dir, f"{prefix}_v*.zip"))
	if not models: 
		return None
	return max(models, key=lambda p: int(p.split('_v')[-1].split('.zip')[0]))

def make_env():
	"""Helper function to instantiate a single environment for the vectorized wrapper."""
	return DuckChessEnvStage10()

def train_stage10(total_timesteps=4_000_000):
	"""Stage 10 V3: High-Mobility & Endgame Optimization with Multiprocessing."""
	base_dir = os.path.join("models", "duck_ppo")
	stage9_dir = os.path.join(base_dir, "stage 9")
	stage10_dir = os.path.join(base_dir, "stage 10")
	
	os.makedirs(stage10_dir, exist_ok=True)
	
	n_envs = 8 
	
	vec_env = make_vec_env(make_env, n_envs=n_envs, vec_env_cls=SubprocVecEnv)
	
	custom_objects = {"learning_rate": 1e-5, "ent_coef": 0.002, "clip_range": 0.15}
	
	latest_s10 = get_latest_model(stage10_dir, "stage10_league")
	if latest_s10:
		print(f"Resuming Stage 10 V3 from: {latest_s10}")
		model = MaskablePPO.load(latest_s10, env=vec_env, tensorboard_log="./tensorboard_logs/Stage10_V3/", custom_objects=custom_objects)
	else:
		base_model = os.path.join(stage9_dir, "stage9_selfplay_latest.zip")
		print(f"Starting Stage 10 V3 cleanly from Baseline: {base_model}")
		model = MaskablePPO.load(base_model, env=vec_env, tensorboard_log="./tensorboard_logs/Stage10_V3/", custom_objects=custom_objects)
		
		vec_env.env_method("set_opponents", base_model, base_model)
	
	callback = LeagueCallback(update_freq=50000, verbose=1)
	model.learn(total_timesteps=total_timesteps, reset_num_timesteps=False, tb_log_name="run_stage10_v3", callback=callback)
	
	model.save(os.path.join(stage10_dir, "stage10_league_latest"))

if __name__ == "__main__":
	train_stage10()