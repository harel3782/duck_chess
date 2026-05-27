import os
import sys
import glob
import argparse
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pygame")
import random
import torch
from concurrent.futures import ThreadPoolExecutor, as_completed
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


# Model Number 7 -> the stage-7 ("robust") checkpoint.
MODEL_7_PATH = os.path.join("models", "duck_ppo", "stage 7", "stage7_robust_latest.zip")


def play_model7_vs_peter(num_games=1, deterministic=True):
	"""Run Model 7 (stage 7) live against Peter's Duck Chess analysis site.

	Loads the stage-7 checkpoint and plays it through DuckPeterEnv, which drives
	the browser via the orientation-aware PeterSiteConnector. Imported lazily so
	the stage-11 trainer above does not require Playwright to be installed.
	"""
	from DuckChess_Game.playwright_game.New.duck_peter_env import DuckPeterEnv

	if not os.path.exists(MODEL_7_PATH):
		print(f"[!] Model 7 checkpoint not found: {MODEL_7_PATH}")
		return

	print(f"Loading Model 7: {MODEL_7_PATH}")
	model = MaskablePPO.load(MODEL_7_PATH, device="cpu")

	env = DuckPeterEnv()
	try:
		for game in range(num_games):
			obs, _ = env.reset()
			terminated = truncated = False
			total_reward = 0.0
			while not (terminated or truncated):
				masks = env.action_masks()
				action, _ = model.predict(obs, action_masks=masks, deterministic=deterministic)
				obs, reward, terminated, truncated, _ = env.step(int(action))
				total_reward += reward
			print(f"[GAME {game + 1}/{num_games}] reward={total_reward:.3f} "
				  f"winner={getattr(env.engine, 'winner', None)}")
	finally:
		env.connector.close()


def _run_one_game(args):
	"""Worker target for a single parallel game. Loads its own model + browser."""
	game_index, deterministic = args
	from DuckChess_Game.playwright_game.New.duck_peter_env import DuckPeterEnv
	model = MaskablePPO.load(MODEL_7_PATH, device="cpu")
	env = DuckPeterEnv()
	try:
		obs, _ = env.reset()
		terminated = truncated = False
		total_reward = 0.0
		while not (terminated or truncated):
			masks = env.action_masks()
			action, _ = model.predict(obs, action_masks=masks, deterministic=deterministic)
			obs, reward, terminated, truncated, _ = env.step(int(action))
			total_reward += reward
		winner = getattr(env.engine, 'winner', None)
		print(f"[GAME {game_index}] reward={total_reward:.3f} winner={winner}")
		return game_index, total_reward, winner
	finally:
		env.connector.close()


def play_model7_vs_peter_parallel(num_games=8, deterministic=True):
	"""Run `num_games` simultaneous games, each in its own thread + browser."""
	if not os.path.exists(MODEL_7_PATH):
		print(f"[!] Model 7 checkpoint not found: {MODEL_7_PATH}")
		return

	print(f"Starting {num_games} parallel games (Model 7 vs Peter)...")
	with ThreadPoolExecutor(max_workers=num_games) as executor:
		futures = {
			executor.submit(_run_one_game, (i + 1, deterministic)): i
			for i in range(num_games)
		}
		for future in as_completed(futures):
			try:
				future.result()
			except Exception as exc:
				print(f"[!] Game {futures[future] + 1} raised: {exc}")

	print("All parallel games finished.")


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Duck Chess training / evaluation runner")
	subparsers = parser.add_subparsers(dest="mode", help="Mode to run")

	# --- train ---
	subparsers.add_parser("train", help="Resume stage-11 self-play league training")

	# --- play (single sequential) ---
	p_play = subparsers.add_parser("play", help="Play Model 7 vs Peter (sequential games)")
	p_play.add_argument("--games", type=int, default=1, help="Number of games (default: 1)")
	p_play.add_argument("--stochastic", action="store_true", help="Use stochastic (non-deterministic) play")

	# --- parallel (8 simultaneous browsers) ---
	p_par = subparsers.add_parser("parallel", help="Play Model 7 vs Peter in parallel browsers")
	p_par.add_argument("--games", type=int, default=8, help="Number of simultaneous games (default: 8)")
	p_par.add_argument("--stochastic", action="store_true", help="Use stochastic play")

	args = parser.parse_args()

	if args.mode == "train":
		train()
	elif args.mode == "play":
		play_model7_vs_peter(num_games=args.games, deterministic=not args.stochastic)
	elif args.mode == "parallel":
		play_model7_vs_peter_parallel(num_games=args.games, deterministic=not args.stochastic)
	else:
		parser.print_help()