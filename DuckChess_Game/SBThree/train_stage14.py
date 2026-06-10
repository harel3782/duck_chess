import os
import glob
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage14_recovery import DuckChessEnvStage14


class ProgressiveRecoveryCallback(BaseCallback):
	"""
	Checkpoint callback for Stage 14. Saves periodic snapshots.
	Unlike Stage 13, uses normalized hyperparameters for stability.
	"""

	def __init__(self, update_freq: int = 500_000):
		super().__init__()
		self.update_freq = update_freq

	def _on_step(self) -> bool:
		"""Fire every update_freq timesteps."""
		if self.num_timesteps % self.update_freq == 0 and self.num_timesteps > 0:
			# Create checkpoint directory
			path = os.path.join("models", "duck_ppo", "stage 14")
			os.makedirs(path, exist_ok=True)

			# Save versioned checkpoint
			version = self.num_timesteps // self.update_freq
			checkpoint_path = os.path.join(path, f"stage14_recovery_v{version}.zip")
			self.model.save(checkpoint_path)

			print(f"[{self.num_timesteps}] Saved Stage 14 checkpoint: {os.path.basename(checkpoint_path)}")

		return True


def make_env(rank):
	"""Factory closure for SubprocVecEnv."""
	def _init():
		return DuckChessEnvStage14(env_index=rank)
	return _init


def train():
	"""
	Stage 14: Progressive Recovery.
	Base: stage13_shock_v224 (recovered entropy, high exploration).
	Goal: Consolidate and stabilize the recovered policy with moderate hyperparameters.
	Duration: 20M steps (longer, more stable training).
	Opponent: Balanced 50% AlphaBeta + 50% Random (less harsh than Stage 13).
	Checkpoint Recovery: Automatically resumes from latest Stage 14 checkpoint if exists.
	"""

	# Smart checkpoint recovery: check for existing Stage 14 checkpoints first
	stage14_checkpoints = glob.glob("models/duck_ppo/stage 14/stage14_recovery_v*.zip")
	if stage14_checkpoints:
		# Sort by version number and take latest
		stage14_checkpoints = sorted(
			stage14_checkpoints,
			key=lambda x: int(x.split('v')[-1].replace('.zip', ''))
		)
		base_model = stage14_checkpoints[-1]
		print(f"Resuming from latest Stage 14 checkpoint: {os.path.basename(base_model)}")
	else:
		# Fallback to Stage 13 base model
		base_model = "models/duck_ppo/stage 13/stage13_shock_v224.zip"
		if os.path.exists(base_model):
			print(f"Loading Stage 13 base model: {base_model}")
		else:
			print(f"ERROR: No Stage 14 checkpoints found and Stage 13 base model not found")
			return

	if not os.path.exists(base_model):
		print(f"ERROR: Base model not found: {base_model}")
		return

	# Setup parallel environments
	n_envs = 8
	vec_env = SubprocVecEnv([make_env(i) for i in range(n_envs)])

	# Progressive hyperparameters: reduced aggression, stabilized learning
	custom_objects = {
		"learning_rate": 2e-5,   # Reduce from 1e-4: 2x Stage 12, not 20x
		"ent_coef": 0.02,        # Reduce from 0.05: 20x Stage 12, not 50x
		"n_steps": 1024,         # Increase from 512: less frequent updates
		"batch_size": 512,       # Increase from 256: match n_steps scale
		"target_kl": 0.05,       # Re-enable KL constraint: prevent policy drift
	}

	# Load and configure model
	model = MaskablePPO.load(
		base_model,
		env=vec_env,
		tensorboard_log="./tensorboard_logs/Stage14_Recovery/",
		custom_objects=custom_objects,
	)

	print("Model loaded with Progressive Recovery hyperparameters:")
	print(f"  learning_rate={custom_objects['learning_rate']}")
	print(f"  ent_coef={custom_objects['ent_coef']}")
	print(f"  n_steps={custom_objects['n_steps']}")
	print(f"  batch_size={custom_objects['batch_size']}")
	print(f"  target_kl={custom_objects['target_kl']}")

	# Setup callback: save every 500K steps
	callback = ProgressiveRecoveryCallback(update_freq=500_000)

	# Train: longer, more stable consolidation phase
	print("\nStarting Stage 14 training (20M steps)...")
	model.learn(
		total_timesteps=20_000_000,
		callback=callback,
		tb_log_name="run_stage14_recovery",
		reset_num_timesteps=False,  # Preserve global timestep count for TensorBoard
	)

	# Final master save
	model.save("models/duck_ppo/stage 14/stage14_recovery_master")
	print("\nStage 14 training complete. Master checkpoint saved.")


if __name__ == "__main__":
	train()
