import os
import glob
import random
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage12_final import DuckChessEnvStage12

class FinalLeagueCallback(BaseCallback):
	"""Handles dynamic pool updates for extreme long-term training."""
	def __init__(self, update_freq=1000000):
		super().__init__()
		self.update_freq = update_freq

	def _on_step(self) -> bool:
		if self.num_timesteps % self.update_freq == 0:
			path = os.path.join("models", "duck_ppo", "stage 12")
			os.makedirs(path, exist_ok=True)
			curr_model = os.path.join(path, f"stage12_final_v{self.num_timesteps // self.update_freq}.zip")
			self.model.save(curr_model)
			
			all_m = glob.glob(os.path.join("models", "duck_ppo", "stage *", "*.zip"))
			hist = random.choice(all_m) if all_m else None
			
			self.training_env.env_method("set_opponents", curr_model, hist)
			print(f"[{self.num_timesteps}] League Updated | Latest: {os.path.basename(curr_model)}")
			
		return True

def make_env(rank):
	def _init():
		return DuckChessEnvStage12(env_index=rank)
	return _init

def train():
	n_envs = 8 # Adjust based on server CPU cores
	vec_env = SubprocVecEnv([make_env(i) for i in range(n_envs)])
	
	base_models = glob.glob("models/duck_ppo/stage 11/*.zip")
	base_model = base_models[-1] if base_models else None
	
	if not base_model:
		print("ERROR: No base model found in stage 11.")
		return

	print(f"Loading Base: {base_model}")
	
	# Reduced learning rate and entropy for late-stage refinement
	custom_objects = {"learning_rate": 5e-6, "ent_coef": 0.001, "target_kl": 0.03}
	
	model = MaskablePPO.load(
		base_model, 
		env=vec_env, 
		tensorboard_log="./tensorboard_logs/Stage12_Final/",
		custom_objects=custom_objects
	)
	
	callback = FinalLeagueCallback(update_freq=1_000_000)
	model.learn(total_timesteps=50_000_000, callback=callback, tb_log_name="run_stage12_final", reset_num_timesteps=False)
	model.save("models/duck_ppo/stage 12/stage12_final_master")

if __name__ == "__main__":
	train()