#!/usr/bin/env python
"""
train_stage13.py — Stage 13: Peter depth-2 + Stage-12 league, time-bounded run.

Opponent mix (heterogeneous SubprocVecEnv):
  ~40% PeterLocalEnv (depth 2)
      → The local Peter engine plays EVERY move via pyo3 bindings.
        PeterLocalEnv mirrors each half-move to Peter's shadow engine so the
        two game states stay in sync.  Peter's coordinate system (a1=0) is
        converted transparently by peter_local.py.  This is a real chess engine
        opponent — not a learned model.

  ~60% DuckChessEnvStage13 (LeagueOpponent backed by stage-12 model weights)
      → Opponents are actual MaskablePPO stage-12 models loaded from disk.
        The callback pre-seeds them at _on_training_start with the latest
        stage-12 checkpoint so they are playing real model-12 moves from
        step 0.  Over time the "latest" slot is updated to this run's own
        improving checkpoints.

set_opponents() is a no-op on PeterLocalEnv (PeterLocalOpponent.set_model
is a no-op), so both env types safely coexist in the same SubprocVecEnv.

Usage:
  python -m DuckChess_Game.SBThree.train_stage13
  python -m DuckChess_Game.SBThree.train_stage13 --base-model "models/duck_ppo/strong/strong_final.zip"
  python -m DuckChess_Game.SBThree.train_stage13 --hours 12 --n-envs 8
"""
from __future__ import annotations

import argparse
import glob
import os
import random
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.duck_env_stage13 import DuckChessEnvStage13
from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config

SAVE_DIR = os.path.join("models", "duck_ppo", "stage 13")

# Stage-12 models are the "real model-12" opponents for league envs.
# Stage-13 checkpoints are added to the pool as training progresses.
HIST_GLOBS = [
    os.path.join("models", "duck_ppo", "stage 12", "*.zip"),
    os.path.join("models", "duck_ppo", "stage 13", "*.zip"),
]

# Best available base model (tried in order; first that exists wins)
DEFAULT_BASE_CANDIDATES = [
    os.path.join("models", "duck_ppo", "strong", "strong_final.zip"),
    os.path.join("models", "duck_ppo", "strong", "strong_latest.zip"),
    os.path.join("models", "duck_ppo", "stage 12", "stage12_final_v52.zip"),
    os.path.join("models", "duck_ppo", "stage 12", "stage12_final_v51.zip"),
]


def _find_default_base() -> str | None:
    for p in DEFAULT_BASE_CANDIDATES:
        if os.path.exists(p):
            return p
    # Fallback: latest stage-12 checkpoint by modification time
    s12 = glob.glob(os.path.join("models", "duck_ppo", "stage 12", "*.zip"))
    if s12:
        return max(s12, key=os.path.getmtime)
    return None


def _hist_pool() -> list[str]:
    pool = []
    for g in HIST_GLOBS:
        pool.extend(glob.glob(g))
    return pool


def make_env(rank: int, role: str):
    """Factory for a Monitor-wrapped env.  role in {'peter2', 'league13'}."""
    def _init():
        if role == "peter2":
            # Real Peter engine opponent — PeterLocalEnv keeps Peter's shadow
            # game in sync via mirror_action() on every half-move.
            env = PeterLocalEnv(
                make_peter_config(depth=2, stage_name="peter_d2"),
                env_index=rank,
            )
        else:
            # Stage-13 league env — LeagueOpponent backed by stage-12 models.
            # set_opponents() is called at training start to load actual model
            # weights so the opponent never falls back to random.
            env = DuckChessEnvStage13(env_index=rank)
        return Monitor(env)
    return _init


def build_roles(n_envs: int) -> list[str]:
    """~40% Peter depth-2, ~60% stage-13 league."""
    n_peter = max(1, (2 * n_envs) // 5)
    n_league = n_envs - n_peter
    return ["peter2"] * n_peter + ["league13"] * n_league


class Stage13Callback(BaseCallback):
    """Versioned checkpoints + stage-12 league pool refresh + time stop."""

    def __init__(self, save_dir: str, checkpoint_every: int, hours: float, base_model: str | None):
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

        # Pre-seed league opponents with actual stage-12 model weights so
        # they play real model-12 moves from step 0 (not random fallback).
        pool = _hist_pool()
        hist = random.choice(pool) if pool else None
        seed_latest = self.base_model if (self.base_model and os.path.exists(self.base_model)) else None

        # If no latest seed, pick the newest stage-12 checkpoint
        if seed_latest is None:
            s12 = glob.glob(os.path.join("models", "duck_ppo", "stage 12", "*.zip"))
            if s12:
                seed_latest = max(s12, key=os.path.getmtime)

        try:
            self.training_env.env_method("set_opponents", seed_latest, hist)
            print(
                f"[stage13] Pre-seeded league opponents | "
                f"latest={os.path.basename(seed_latest) if seed_latest else None} "
                f"hist={os.path.basename(hist) if hist else None}"
            )
        except Exception as exc:
            print(f"[stage13] seed set_opponents failed: {exc}")

    def _on_step(self) -> bool:
        now = time.time()

        # Versioned checkpoint + league refresh
        if self.num_timesteps - self.version * self.checkpoint_every >= self.checkpoint_every:
            self.version += 1
            ckpt = os.path.join(self.save_dir, f"stage13_v{self.version}.zip")
            self.model.save(ckpt)
            self.model.save(os.path.join(self.save_dir, "stage13_latest.zip"))
            self.last_latest_save = now

            # Update league envs: latest = newest stage-13 ckpt,
            # historical = random from full pool (stage-12 + stage-13 so far)
            pool = _hist_pool()
            hist = random.choice(pool) if pool else None
            try:
                self.training_env.env_method("set_opponents", ckpt, hist)
            except Exception:
                pass

            elapsed = (now - self.start) / 3600.0
            fps = self.num_timesteps / max(1e-9, now - self.start)
            print(
                f"[stage13] step={self.num_timesteps:,} v{self.version} saved | "
                f"{elapsed:.2f}h | {fps:.0f} steps/s | "
                f"hist={os.path.basename(hist) if hist else None}"
            )

        # Crash-safe latest every 15 min
        elif now - self.last_latest_save > 900:
            self.model.save(os.path.join(self.save_dir, "stage13_latest.zip"))
            self.last_latest_save = now

        # Time-based stop
        if now >= self.deadline:
            print(f"[stage13] Time budget reached ({(now - self.start)/3600.0:.2f}h). Stopping.")
            return False
        return True


def main():
    p = argparse.ArgumentParser(description="Stage 13: Peter + Stage-12 league training")
    p.add_argument("--base-model", default=None, help="Warm-start checkpoint (.zip)")
    p.add_argument("--hours", type=float, default=11.5, help="Wall-clock budget in hours (default 11.5)")
    p.add_argument("--n-envs", type=int, default=8, help="Parallel envs (default 8)")
    p.add_argument("--checkpoint-every", type=int, default=500_000, help="Steps between versioned saves")
    p.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    p.add_argument("--ent-coef", type=float, default=0.01, help="Entropy coefficient")
    args = p.parse_args()

    os.makedirs(SAVE_DIR, exist_ok=True)

    base = args.base_model
    if base is None:
        base = _find_default_base()
        if base:
            print(f"[stage13] Auto-selected base model: {base}")
        else:
            print("[stage13] No base model found; starting from scratch")

    roles = build_roles(args.n_envs)
    print(f"[stage13] env roles: {roles}")
    print(f"[stage13]   Peter envs (real engine, depth 2): {roles.count('peter2')}")
    print(f"[stage13]   League envs (model-12 opponents):  {roles.count('league13')}")

    vec_env = SubprocVecEnv([make_env(i, roles[i]) for i in range(args.n_envs)])

    custom_objects = {
        "learning_rate": args.lr,
        "ent_coef": args.ent_coef,
        "target_kl": 0.05,
    }

    if base and os.path.exists(base):
        print(f"[stage13] Warm-starting from: {base}")
        model = MaskablePPO.load(
            base,
            env=vec_env,
            tensorboard_log="./tensorboard_logs/stage13/",
            custom_objects=custom_objects,
        )
    else:
        if base:
            print(f"[stage13] Base model not found ({base}); starting FRESH")
        model = MaskablePPO(
            "MlpPolicy",
            vec_env,
            learning_rate=args.lr,
            ent_coef=args.ent_coef,
            target_kl=0.05,
            n_steps=512,
            batch_size=256,
            verbose=1,
            tensorboard_log="./tensorboard_logs/stage13/",
        )

    cb = Stage13Callback(SAVE_DIR, args.checkpoint_every, args.hours, base)
    print(f"[stage13] Starting: {args.hours}h budget | lr={args.lr} | ent={args.ent_coef} | {args.n_envs} envs")
    model.learn(
        total_timesteps=1_000_000_000,  # time-bounded; Stage13Callback stops it
        callback=cb,
        tb_log_name="stage13",
        reset_num_timesteps=True,
    )

    final = os.path.join(SAVE_DIR, "stage13_final.zip")
    model.save(final)
    model.save(os.path.join(SAVE_DIR, "stage13_latest.zip"))
    print(f"[stage13] DONE → {final}")


if __name__ == "__main__":
    main()
