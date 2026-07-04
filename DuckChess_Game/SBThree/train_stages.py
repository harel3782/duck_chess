#!/usr/bin/env python
"""
train_stages.py — League training for Stage 12 (self-play) or Stage 14 (recovery).

Replaces the standalone train_stage12.py and train_stage14.py files.

  Stage 12  Continues from Stage 11 with fine-tuning (lr=5e-6, ent=0.001).
            50M steps, updates league opponents every 1M steps.
  Stage 14  Progressive recovery from Stage 13 shock therapy.
            20M steps, checkpoints every 500K, moderate hyperparameters.

Usage:
  python -m DuckChess_Game.SBThree.train_stages --stage 12
  python -m DuckChess_Game.SBThree.train_stages --stage 14
  python -m DuckChess_Game.SBThree.train_stages --stage 14 --n-envs 4
"""
import os
import glob
import random
import argparse
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage12 import DuckChessEnvStage12
from DuckChess_Game.SBThree.duck_env_stage14_recovery import DuckChessEnvStage14


# ------------------------------------------------------------------ Stage 12

class FinalLeagueCallback(BaseCallback):
    """Dynamic pool updates for stage-12 long-term training."""
    def __init__(self, update_freq=1_000_000):
        super().__init__()
        self.update_freq = update_freq

    def _on_step(self) -> bool:
        if self.num_timesteps % self.update_freq == 0:
            path = os.path.join("models", "duck_ppo", "stage 12")
            os.makedirs(path, exist_ok=True)
            curr_model = os.path.join(
                path, f"stage12_final_v{self.num_timesteps // self.update_freq}.zip"
            )
            self.model.save(curr_model)
            all_m = glob.glob(os.path.join("models", "duck_ppo", "stage *", "*.zip"))
            hist = random.choice(all_m) if all_m else None
            self.training_env.env_method("set_opponents", curr_model, hist)
            print(f"[{self.num_timesteps}] League Updated | Latest: {os.path.basename(curr_model)}")
        return True


def _train_stage12(n_envs):
    def make_env(rank):
        def _init():
            return DuckChessEnvStage12(env_index=rank)
        return _init

    vec_env = SubprocVecEnv([make_env(i) for i in range(n_envs)])

    base_models = glob.glob("models/duck_ppo/stage 12/*.zip")
    if not base_models:
        base_models = glob.glob("models/duck_ppo/stage 11/*.zip")
    if base_models:
        base_models = sorted(base_models, key=lambda x: int(x.split('v')[-1].replace('.zip', '')))
        base_model = base_models[-1]
    else:
        print("ERROR: No base model found in stage 12 or stage 11.")
        return

    print(f"Loading Base: {base_model}")
    model = MaskablePPO.load(
        base_model, env=vec_env,
        tensorboard_log="./tensorboard_logs/Stage12_Final/",
        custom_objects={"learning_rate": 5e-6, "ent_coef": 0.001, "target_kl": 0.03},
    )
    model.learn(
        total_timesteps=50_000_000,
        callback=FinalLeagueCallback(update_freq=1_000_000),
        tb_log_name="run_stage12_final",
        reset_num_timesteps=False,
    )
    model.save("models/duck_ppo/stage 12/stage12_final_master")


# ------------------------------------------------------------------ Stage 14

class ProgressiveRecoveryCallback(BaseCallback):
    """Periodic checkpoint saves for Stage 14 recovery."""
    def __init__(self, update_freq=500_000):
        super().__init__()
        self.update_freq = update_freq

    def _on_step(self) -> bool:
        if self.num_timesteps % self.update_freq == 0 and self.num_timesteps > 0:
            path = os.path.join("models", "duck_ppo", "stage 14")
            os.makedirs(path, exist_ok=True)
            version = self.num_timesteps // self.update_freq
            ckpt = os.path.join(path, f"stage14_recovery_v{version}.zip")
            self.model.save(ckpt)
            print(f"[{self.num_timesteps}] Saved Stage 14 checkpoint: {os.path.basename(ckpt)}")
        return True


def _train_stage14(n_envs):
    def make_env(rank):
        def _init():
            return DuckChessEnvStage14(env_index=rank)
        return _init

    vec_env = SubprocVecEnv([make_env(i) for i in range(n_envs)])

    stage14_checkpoints = glob.glob("models/duck_ppo/stage 14/stage14_recovery_v*.zip")
    if stage14_checkpoints:
        stage14_checkpoints = sorted(
            stage14_checkpoints,
            key=lambda x: int(x.split('v')[-1].replace('.zip', ''))
        )
        base_model = stage14_checkpoints[-1]
        print(f"Resuming from: {os.path.basename(base_model)}")
    else:
        base_model = "models/duck_ppo/stage 13/stage13_shock_v224.zip"
        if not os.path.exists(base_model):
            print("ERROR: No Stage 14 checkpoints found and Stage 13 base not found.")
            return

    model = MaskablePPO.load(
        base_model, env=vec_env,
        tensorboard_log="./tensorboard_logs/Stage14_Recovery/",
        custom_objects={
            "learning_rate": 2e-5, "ent_coef": 0.02,
            "n_steps": 1024, "batch_size": 512, "target_kl": 0.05,
        },
    )
    print(f"Starting Stage 14 training (20M steps) from: {os.path.basename(base_model)}")
    model.learn(
        total_timesteps=20_000_000,
        callback=ProgressiveRecoveryCallback(update_freq=500_000),
        tb_log_name="run_stage14_recovery",
        reset_num_timesteps=False,
    )
    model.save("models/duck_ppo/stage 14/stage14_recovery_master")
    print("Stage 14 training complete. Master checkpoint saved.")


# ------------------------------------------------------------------ Entry

def main():
    p = argparse.ArgumentParser(description="Stage 12 or 14 league training")
    p.add_argument("--stage", type=int, required=True, choices=[12, 14],
                   help="Which curriculum stage to run (12=self-play league, 14=recovery)")
    p.add_argument("--n-envs", type=int, default=8, help="Parallel envs (default 8)")
    args = p.parse_args()

    if args.stage == 12:
        _train_stage12(args.n_envs)
    else:
        _train_stage14(args.n_envs)


if __name__ == "__main__":
    main()
