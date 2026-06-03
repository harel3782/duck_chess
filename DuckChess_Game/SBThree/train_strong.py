#!/usr/bin/env python
"""
train_strong.py — 12-hour "make it strong" run for Duck Chess.

Design goals (informed by benchmarking the env throughput on this machine):

  * Peter depth 3 runs at ~3 steps/s and, because SubprocVecEnv is synchronous,
    a single depth-3 env throttles the WHOLE batch. The earlier peter_local runs
    used depths (1,2,3,3) and crawled at 3-9 fps. We BAN depth 3 here.
  * Peter depth 2 (~72 steps/s) is the strongest fast tactical opponent.
  * The self-play league env (~85 steps/s) is fast and strong and provides
    opponent diversity that prevents over-fitting to one engine.

So the opponent mix is a heterogeneous SubprocVecEnv:
    - a few Peter envs (depth 1 + depth 2)  -> tactical grounding vs a real engine
    - the rest self-play league envs         -> diversity, anti-collapse
The league callback's ``set_opponents`` is a no-op on Peter envs, so the two
env types coexist safely in one vec env.

Critical fix vs the old runs: EVERY env is wrapped in ``Monitor`` so that
``ep_rew_mean`` / ``ep_len_mean`` finally show up in TensorBoard and the console
(the old runs had no Monitor, which is why win-rate was invisible).

The run is TIME-BOUNDED: it stops after ``--hours`` wall-clock and always saves
a final model, so you get a deliverable at the 12-hour mark regardless of speed.

Usage:
  python -m DuckChess_Game.SBThree.train_strong \
      --base-model "models/duck_ppo/stage 12/stage12_final_v52.zip" \
      --hours 11.5
"""
from __future__ import annotations

import os
import sys
import glob
import time
import random
import argparse
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config
from DuckChess_Game.SBThree.duck_env_stage12_final import DuckChessEnvStage12

SAVE_DIR = os.path.join("models", "duck_ppo", "strong")
# Historical league opponents — STRONG snapshots only.
# Evaluation showed the stage-10/12 self-play models lose 0/20 to Peter depth 2,
# so they are deliberately EXCLUDED: using them as opponents would drag the
# (much stronger) Peter-trained policy back toward a weak distribution. We pool
# only the Peter-trained checkpoints and this run's own improving snapshots.
HIST_GLOBS = [
    os.path.join("models", "duck_ppo", "strong", "*.zip"),
    os.path.join("models", "duck_ppo", "peter_local", "*.zip"),
]


def _hist_pool():
    pool = []
    for g in HIST_GLOBS:
        pool.extend(glob.glob(g))
    return pool


def make_env(rank: int, role: str):
    """Factory returning a Monitor-wrapped env. `role` in {'peter1','peter2','league'}."""
    def _init():
        if role == "peter1":
            env = PeterLocalEnv(make_peter_config(depth=1, stage_name="peter_d1"), env_index=rank)
        elif role == "peter2":
            env = PeterLocalEnv(make_peter_config(depth=2, stage_name="peter_d2"), env_index=rank)
        else:
            env = DuckChessEnvStage12(env_index=rank)
        return Monitor(env)  # <-- gives us ep_rew_mean / ep_len_mean
    return _init


def build_roles(n_envs: int):
    """Assign env roles.

    Strategy: ~3/8 depth-2 Peter envs for continued tactical grounding against a
    real engine, the remaining ~5/8 strong self-play league envs (opponent =
    latest + a strong Peter-trained historical snapshot) to provide the HARD,
    diverse opposition that pushes a model which already saturates Peter d2.

    Depth-1 Peter is intentionally omitted: the training log noted the policy
    exploits its 1-ply horizon, which teaches bad habits.
    """
    roles = []
    n_peter2 = max(1, (3 * n_envs) // 8)   # ~37% depth-2 Peter grounding
    n_league = n_envs - n_peter2
    roles += ["peter2"] * n_peter2
    roles += ["league"] * n_league
    return roles


class StrongCallback(BaseCallback):
    """Versioned checkpoints + league pool refresh + crash-safe latest + time stop."""

    def __init__(self, save_dir, checkpoint_every, hours, base_model):
        super().__init__()
        self.save_dir = save_dir
        self.checkpoint_every = checkpoint_every
        self.deadline = time.time() + hours * 3600.0
        self.base_model = base_model
        self.start = time.time()
        self.last_latest_save = time.time()
        self.version = 0

    def _on_training_start(self) -> None:
        os.makedirs(self.save_dir, exist_ok=True)
        # Pre-seed league opponents so we don't waste early steps vs random.
        pool = _hist_pool()
        hist = random.choice(pool) if pool else None
        seed_latest = self.base_model if (self.base_model and os.path.exists(self.base_model)) else None
        try:
            self.training_env.env_method("set_opponents", seed_latest, hist)
            print(f"[strong] Seeded league opponents | latest={os.path.basename(seed_latest) if seed_latest else None} "
                  f"hist={os.path.basename(hist) if hist else None}")
        except Exception as e:
            print(f"[strong] seed set_opponents failed: {e}")

    def _on_step(self) -> bool:
        now = time.time()

        # Versioned checkpoint + league refresh
        if self.num_timesteps - self.version * self.checkpoint_every >= self.checkpoint_every:
            self.version += 1
            ckpt = os.path.join(self.save_dir, f"strong_v{self.version}.zip")
            self.model.save(ckpt)
            self.model.save(os.path.join(self.save_dir, "strong_latest.zip"))
            self.last_latest_save = now
            pool = _hist_pool()
            hist = random.choice(pool) if pool else None
            try:
                self.training_env.env_method("set_opponents", ckpt, hist)
            except Exception:
                pass
            elapsed = (now - self.start) / 3600.0
            fps = self.num_timesteps / max(1e-9, now - self.start)
            print(f"[strong] step={self.num_timesteps:,} v{self.version} saved | "
                  f"{elapsed:.2f}h elapsed | {fps:.0f} steps/s | "
                  f"hist={os.path.basename(hist) if hist else None}")

        # Crash-safe latest every 15 min
        elif now - self.last_latest_save > 900:
            self.model.save(os.path.join(self.save_dir, "strong_latest.zip"))
            self.last_latest_save = now

        # Time-based stop
        if now >= self.deadline:
            print(f"[strong] Reached time budget ({(now - self.start)/3600.0:.2f}h). Stopping.")
            return False
        return True


def main():
    p = argparse.ArgumentParser(description="12-hour strong Duck Chess training")
    p.add_argument("--base-model", default=None, help="Warm-start checkpoint (.zip)")
    p.add_argument("--hours", type=float, default=11.5, help="Wall-clock budget (default 11.5)")
    p.add_argument("--n-envs", type=int, default=8, help="Parallel envs (default 8)")
    p.add_argument("--checkpoint-every", type=int, default=500_000, help="Steps between versioned saves")
    p.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    p.add_argument("--ent-coef", type=float, default=0.01, help="Entropy coefficient")
    args = p.parse_args()

    os.makedirs(SAVE_DIR, exist_ok=True)

    roles = build_roles(args.n_envs)
    print(f"[strong] env roles: {roles}")
    vec_env = SubprocVecEnv([make_env(i, roles[i]) for i in range(args.n_envs)])

    custom_objects = {"learning_rate": args.lr, "ent_coef": args.ent_coef, "target_kl": 0.05}

    base = args.base_model
    if base and os.path.exists(base):
        print(f"[strong] Warm-starting from: {base}")
        model = MaskablePPO.load(
            base, env=vec_env,
            tensorboard_log="./tensorboard_logs/strong/",
            custom_objects=custom_objects,
        )
    else:
        if base:
            print(f"[strong] base model not found ({base}); starting FRESH")
        model = MaskablePPO(
            "MlpPolicy", vec_env,
            learning_rate=args.lr, ent_coef=args.ent_coef, target_kl=0.05,
            n_steps=512, batch_size=256, verbose=1,
            tensorboard_log="./tensorboard_logs/strong/",
        )

    cb = StrongCallback(SAVE_DIR, args.checkpoint_every, args.hours, base)
    print(f"[strong] Starting run: {args.hours}h budget, lr={args.lr}, {args.n_envs} envs")
    model.learn(
        total_timesteps=1_000_000_000,  # effectively unbounded; time stop ends it
        callback=cb,
        tb_log_name="strong",
        reset_num_timesteps=True,
    )
    final = os.path.join(SAVE_DIR, "strong_final.zip")
    model.save(final)
    model.save(os.path.join(SAVE_DIR, "strong_latest.zip"))
    print(f"[strong] DONE -> {final}")


if __name__ == "__main__":
    main()
