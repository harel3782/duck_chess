import os
import glob
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pygame")
import random
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage11_alpha import DuckChessEnvStage11

class LeagueCallback(BaseCallback):
	"""League Management. Only prints once to avoid terminal spam."""
	def __init__(self, update_freq=500000):
		super().__init__()
		self.update_freq = update_freq

	def _on_step(self) -> bool:
		if self.num_timesteps % self.update_freq == 0:
			path = os.path.join("models", "duck_ppo", "stage 11")
			os.makedirs(path, exist_ok=True)
			curr_model = os.path.join(path, f"stage11_sparse_v{self.num_timesteps // self.update_freq}.zip")
			self.model.save(curr_model)
			
			all_m = glob.glob(os.path.join("models", "duck_ppo", "stage *", "*.zip"))
			hist = random.choice(all_m) if all_m else None
			
			# Broadcast to all environments
			self.training_env.env_method("set_opponents", curr_model, hist)
			
			# Only print once!
			print(f"[{self.num_timesteps}] League Updated | Latest: {os.path.basename(curr_model)}")
			
		return True

def make_env(rank):
	"""Closure to inject rank into environment instance."""
	def _init():
		return DuckChessEnvStage11(env_index=rank)
	return _init

def train():
	n_envs = 8 # Update this to 32 or 64 on the college cluster
	
	# Explicitly map environments to IDs (0 to n_envs-1)
	vec_env = SubprocVecEnv([make_env(i) for i in range(n_envs)])
	
	base_model = "models/duck_ppo/stage 10/stage10_league_latest.zip"
	if not os.path.exists(base_model):
		base_models = glob.glob("models/duck_ppo/stage 9/*.zip")
		base_model = base_models[0] if base_models else None

	print(f"Loading Base: {base_model}")
	
	# Added target_kl to prevent excessive "Early Stopping" and allowed higher entropy for exploration
	custom_objects = {"learning_rate": 1e-5, "ent_coef": 0.005, "target_kl": 0.05}
	
	if base_model:
		model = MaskablePPO.load(base_model, env=vec_env, 
								tensorboard_log="./tensorboard_logs/Stage11_Sparse/",
								custom_objects=custom_objects)
	else:
		print("No base model found. Exiting.")
		return
	
	callback = LeagueCallback(update_freq=500000)
	model.learn(total_timesteps=10_000_000, callback=callback, tb_log_name="run_stage11_sparse")
	model.save("models/duck_ppo/stage 12/stage12_final_v24")

if __name__ == "__main__":
	train()