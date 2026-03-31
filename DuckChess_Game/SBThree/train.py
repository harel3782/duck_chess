import os
import glob
import random
import torch
from stable_baselines3 import PPO
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import CheckpointCallback, BaseCallback

# Disable PyTorch strict validation to prevent float32 Simplex() crashes
torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage7_robust import DuckChessEnvStage7

class PoolOpponentCallback(BaseCallback):
	"""Randomly selects an opponent from the history pool to prevent overfitting."""
	def __init__(self, env, update_freq=50000, verbose=0):
		super().__init__(verbose)
		self.env = env
		self.update_freq = update_freq

	def _on_step(self) -> bool:
		if self.num_timesteps % self.update_freq == 0:
			stage7_dir = os.path.join("models", "duck_ppo", "stage 7")
			current_path = os.path.join(stage7_dir, f"stage7_robust_v{self.num_timesteps // self.update_freq}.zip")
			self.model.save(current_path)
			
			# Pick a random historical model from ANY stage directory
			all_models = glob.glob(os.path.join("models", "duck_ppo", "stage *", "*.zip"))
			if all_models:
				chosen_opponent = random.choice(all_models)
				self.env.set_opponent(chosen_opponent)
				if self.verbose > 0:
					print(f"[{self.num_timesteps}] Opponent swapped to historical version: {os.path.basename(chosen_opponent)}")
		return True

def get_latest_model(model_dir, prefix):
	"""Finds the most recent model based on the 'vX' numbering in a specific directory."""
	models = glob.glob(os.path.join(model_dir, f"{prefix}_v*.zip"))
	if not models:
		return None
	latest_model = max(models, key=lambda p: int(p.split('_v')[-1].split('.zip')[0]))
	return latest_model

def train_stage7(total_timesteps=3_000_000):
	"""Stage 7: Robustness Training against an Opponent Pool."""
	env = DuckChessEnvStage7()
	
	base_models_dir = os.path.join("models", "duck_ppo")
	stage7_dir = os.path.join(base_models_dir, "stage 7")
	stage6_dir = os.path.join(base_models_dir, "stage 6")
	
	os.makedirs(stage7_dir, exist_ok=True)
	
	custom_objects = {
		"learning_rate": 1e-5,
		"ent_coef": 0.001,
		"clip_range": 0.15
	}
	
	latest_stage7 = get_latest_model(stage7_dir, "stage7_robust")
	
	if latest_stage7:
		print(f"Resuming Stage 7 from: {latest_stage7}")
		model = MaskablePPO.load(
			latest_stage7, 
			env=env, 
			tensorboard_log="./tensorboard_logs/Stage7_Combined/",
			custom_objects=custom_objects
		)
		env.set_opponent(latest_stage7)
	else:
		base_model = os.path.join(stage6_dir, "stage6_advanced_latest.zip")
		if not os.path.exists(base_model):
			print(f"Error: Base model {base_model} not found!")
			return
			
		print(f"Loading Stage 6 model ({base_model}) to start Robustness training...")
		model = MaskablePPO.load(
			base_model, 
			env=env, 
			tensorboard_log="./tensorboard_logs/Stage7_Combined/", 
			custom_objects=custom_objects
		)
		env.set_opponent(base_model)
	
	pool_callback = PoolOpponentCallback(env.unwrapped, update_freq=50000, verbose=1)
	
	print(f"Starting Stage 7 Training for {total_timesteps} timesteps...")
	model.learn(
		total_timesteps=total_timesteps, 
		reset_num_timesteps=False, 
		tb_log_name="run_stage7_robust",
		callback=pool_callback
	)
	
	model.save(os.path.join(stage7_dir, "stage7_robust_latest"))
	print("Stage 7 Training Complete.")

if __name__ == "__main__":
	train_stage7(total_timesteps=3_000_000)