import os
import glob
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage13_fast import DuckChessEnvStage13


class ShockTherapyCallback(BaseCallback):
	"""
	Checkpoint callback for Stage 13. Saves periodic snapshots.
	Unlike Stage 12, does NOT update opponent pool (static opponents).
	"""

	def __init__(self, update_freq: int = 500_000):
		super().__init__()
		self.update_freq = update_freq

	def _on_step(self) -> bool:
		"""Fire every update_freq timesteps."""
		if self.num_timesteps % self.update_freq == 0 and self.num_timesteps > 0:
			# Create checkpoint directory
			path = os.path.join("models", "duck_ppo", "stage 13")
			os.makedirs(path, exist_ok=True)

			# Save versioned checkpoint
			version = self.num_timesteps // self.update_freq
			checkpoint_path = os.path.join(path, f"stage13_shock_v{version}.zip")
			self.model.save(checkpoint_path)

			print(f"[{self.num_timesteps}] Saved Stage 13 checkpoint: {os.path.basename(checkpoint_path)}")

		return True


def make_env(rank):
	"""Factory closure for SubprocVecEnv."""
	def _init():
		return DuckChessEnvStage13(env_index=rank)
	return _init


def train():
	"""
	Stage 13: Shock Therapy.
	Base: stage12_final_v102 (degraded, sparse-reward trained).
	Goal: High-efficiency recovery via aggressive hyperparameters and dense tactical rewards.
	Duration: 10M steps (short, focused).
	Opponent: Fixed 50% AlphaBeta + 50% Stage 11 reference (no self-play).
	Checkpoint Recovery: Automatically resumes from latest Stage 13 checkpoint if exists.
	"""

	# Smart checkpoint recovery: check for existing Stage 13 checkpoints first
	stage13_checkpoints = glob.glob("models/duck_ppo/stage 13/stage13_shock_v*.zip")
	if stage13_checkpoints:
		# Sort by version number and take latest
		stage13_checkpoints = sorted(
			stage13_checkpoints,
			key=lambda x: int(x.split('v')[-1].replace('.zip', ''))
		)
		base_model = stage13_checkpoints[-1]
		print(f"Resuming from latest Stage 13 checkpoint: {os.path.basename(base_model)}")
	else:
		# Fallback to Stage 12 base model
		base_model = "models/duck_ppo/stage 12/stage12_final_v102.zip"
		if os.path.exists(base_model):
			print(f"Loading Stage 12 base model: {base_model}")
		else:
			print(f"ERROR: No Stage 13 checkpoints found and Stage 12 base model not found")
			return

	if not os.path.exists(base_model):
		print(f"ERROR: Base model not found: {base_model}")
		return

	# Setup parallel environments
	n_envs = 8
	vec_env = SubprocVecEnv([make_env(i) for i in range(n_envs)])

	# Aggressive hyperparameters for shock therapy
	custom_objects = {
		"learning_rate": 1e-4,  # 20x Stage 12: fast weight adjustment
		"ent_coef": 0.05,       # 50x Stage 12: maximized exploration
		"n_steps": 512,         # Frequent updates: 4096 step rollout per cycle (8 envs × 512)
		"batch_size": 256,      # 16 minibatches per update
		"target_kl": None,      # No early stopping: allow large policy steps
	}

	# Load and configure model
	model = MaskablePPO.load(
		base_model,
		env=vec_env,
		tensorboard_log="./tensorboard_logs/Stage13_ShockTherapy/",
		custom_objects=custom_objects,
	)

	print("Model loaded with Shock Therapy hyperparameters:")
	print(f"  learning_rate={custom_objects['learning_rate']}")
	print(f"  ent_coef={custom_objects['ent_coef']}")
	print(f"  n_steps={custom_objects['n_steps']}")
	print(f"  batch_size={custom_objects['batch_size']}")
	print(f"  target_kl={custom_objects['target_kl']}")

	# Setup callback: save every 500K steps
	callback = ShockTherapyCallback(update_freq=500_000)

	# Train: short, intensive recovery phase
	print("\nStarting Stage 13 training (10M steps)...")
	model.learn(
		total_timesteps=10_000_000,
		callback=callback,
		tb_log_name="run_stage13_shock",
		reset_num_timesteps=False,  # Preserve global timestep count for TensorBoard
	)

	# Final master save
	model.save("models/duck_ppo/stage 13/stage13_shock_master")
	print("\nStage 13 training complete. Master checkpoint saved.")


if __name__ == "__main__":
	train()
