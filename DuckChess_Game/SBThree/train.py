import os
import glob
import torch
from stable_baselines3 import PPO
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import CheckpointCallback, BaseCallback

# Disable PyTorch strict validation to prevent float32 Simplex() crashes
torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage6_advanced import DuckChessEnvStage6

class SyncOpponentCallback(BaseCallback):
	"""Regularly updates the self-play opponent with the latest model."""
	def __init__(self, env, update_freq=50000, verbose=0):
		super().__init__(verbose)
		self.env = env
		self.update_freq = update_freq

	def _on_step(self) -> bool:
		if self.num_timesteps % self.update_freq == 0:
			model_path = os.path.join("models", "duck_ppo", f"stage6_advanced_v{self.num_timesteps // self.update_freq}.zip")
			self.model.save(model_path)
			self.env.set_opponent(model_path)
			if self.verbose > 0:
				print(f"[{self.num_timesteps}] Opponent updated to {model_path}")
		return True

def get_latest_model(model_dir, prefix):
	"""Finds the most recent model based on the 'vX' numbering."""
	models = glob.glob(os.path.join(model_dir, f"{prefix}_v*.zip"))
	if not models:
		return None
	latest_model = max(models, key=lambda p: int(p.split('_v')[-1].split('.zip')[0]))
	return latest_model

def train_stage6(total_timesteps=2_000_000):
	"""Stage 6: Strategic Mastery with Time Penalties."""
	env = DuckChessEnvStage6()
	model_dir = os.path.join("models", "duck_ppo")
	os.makedirs(model_dir, exist_ok=True)
	
	# Adjust parameters to keep training stable
	custom_objects = {
		"learning_rate": 1e-5,
		"ent_coef": 0.001,
		"clip_range": 0.15
	}
	
	latest_stage6 = get_latest_model(model_dir, "stage6_advanced")
	
	if latest_stage6:
		print(f"Resuming Stage 6 from the latest checkpoint: {latest_stage6}")
		model = MaskablePPO.load(
			latest_stage6, 
			env=env, 
			tensorboard_log="./tensorboard_logs/Stage6_Combined/",
			custom_objects=custom_objects
		)
		env.set_opponent(latest_stage6)
	else:
		latest_stage5 = get_latest_model(model_dir, "stage5_strategic")
		if not latest_stage5:
			latest_stage5 = os.path.join(model_dir, "stage5_strategic_latest.zip")
			
		if not os.path.exists(latest_stage5):
			print(f"Error: Base model {latest_stage5} not found!")
			return
			
		print(f"Loading Stage 5 model ({latest_stage5}) as the foundation for Stage 6...")
		model = MaskablePPO.load(
			latest_stage5, 
			env=env, 
			tensorboard_log="./tensorboard_logs/Stage6_Combined/", 
			custom_objects=custom_objects
		)
		env.set_opponent(latest_stage5)
	
	sync_callback = SyncOpponentCallback(env.unwrapped, update_freq=50000, verbose=1)
	
	print(f"Starting Stage 6 Training for {total_timesteps} timesteps...")
	model.learn(
		total_timesteps=total_timesteps, 
		reset_num_timesteps=False, 
		tb_log_name="run_stage6_advanced",
		callback=sync_callback
	)
	
	model.save(os.path.join(model_dir, "stage6_advanced_latest"))
	print("Stage 6 Training Complete.")

if __name__ == "__main__":
	train_stage6(total_timesteps=2_000_000)