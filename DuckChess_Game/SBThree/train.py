import os
import glob
import random
import torch
from stable_baselines3 import PPO
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback

# Disable PyTorch strict validation to prevent float32 Simplex() crashes
torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage9_selfplay import DuckChessEnvStage9

class StrictSelfPlayCallback(BaseCallback):
	"""Updates the opponent to always be the absolute latest saved model."""
	def __init__(self, env, update_freq=50000, verbose=0):
		super().__init__(verbose)
		self.env = env
		self.update_freq = update_freq

	def _on_step(self) -> bool:
		if self.num_timesteps % self.update_freq == 0:
			# Save the current model to the stage 9 directory
			stage9_dir = os.path.join("models", "duck_ppo", "stage 9")
			os.makedirs(stage9_dir, exist_ok=True)
			
			current_path = os.path.join(stage9_dir, f"stage9_selfplay_v{self.num_timesteps // self.update_freq}.zip")
			self.model.save(current_path)
			
			# Immediately load this newly saved model as the opponent
			self.env.set_opponent(current_path)
			
			if self.verbose > 0:
				print(f"[{self.num_timesteps}] Opponent updated to the absolute latest version: {os.path.basename(current_path)}")
		return True

def get_latest_model(model_dir, prefix):
	"""Finds the most recent model based on the 'vX' numbering in a specific directory."""
	models = glob.glob(os.path.join(model_dir, f"{prefix}_v*.zip"))
	if not models:
		return None
	latest_model = max(models, key=lambda p: int(p.split('_v')[-1].split('.zip')[0]))
	return latest_model

def train_stage9(total_timesteps=3_000_000):
	"""Stage 9: Pure Self-Play Training."""
	env = DuckChessEnvStage9()
	
	base_models_dir = os.path.join("models", "duck_ppo")
	stage9_dir = os.path.join(base_models_dir, "stage 9")
	stage8_dir = os.path.join(base_models_dir, "stage 8")
	
	os.makedirs(stage9_dir, exist_ok=True)
	
	custom_objects = {
		"learning_rate": 1e-5,
		"ent_coef": 0.001,
		"clip_range": 0.15
	}
	
	latest_stage9 = get_latest_model(stage9_dir, "stage9_selfplay")
	
	if latest_stage9:
		print(f"Resuming Stage 9 from: {latest_stage9}")
		model = MaskablePPO.load(
			latest_stage9, 
			env=env, 
			tensorboard_log="./tensorboard_logs/Stage9_Combined/",
			custom_objects=custom_objects
		)
		env.set_opponent(latest_stage9)
	else:
		# Start fresh from the best Stage 8 model
		base_model = get_latest_model(stage8_dir, "stage8_positional")
		if not base_model or not os.path.exists(base_model):
			# Fallback to the latest explicit zip if dynamic search fails
			base_model = os.path.join(stage8_dir, "stage8_positional_latest.zip")
			if not os.path.exists(base_model):
				print(f"Error: Base model {base_model} not found! Please check the path.")
				return
				
		print(f"Loading Stage 8 model ({base_model}) to start Pure Self-Play training...")
		model = MaskablePPO.load(
			base_model, 
			env=env, 
			tensorboard_log="./tensorboard_logs/Stage9_Combined/", 
			custom_objects=custom_objects
		)
		env.set_opponent(base_model)
	
	# Use the Strict Self-Play Callback
	sp_callback = StrictSelfPlayCallback(env.unwrapped, update_freq=50000, verbose=1)
	
	print(f"Starting Stage 9 Training for {total_timesteps} timesteps...")
	model.learn(
		total_timesteps=total_timesteps, 
		reset_num_timesteps=False, 
		tb_log_name="run_stage9_selfplay",
		callback=sp_callback
	)
	
	model.save(os.path.join(stage9_dir, "stage9_selfplay_latest"))
	print("Stage 9 Training Complete.")

if __name__ == "__main__":
	train_stage9(total_timesteps=3_000_000)