#!/usr/bin/env python
"""
train_peter_v2.py — v2 training run: opponent pool + random starts + sparse reward.

See PLAN_V2.md for the full rationale. In short, v1 runs produced a king-rush
exploit because they trained vs a single fixed Peter depth from a fixed start
position. v2 samples the opponent per episode (Peter d1/d2/d3, self-play
latest, historical checkpoint, random mover), randomizes starting positions,
and uses sparse terminal reward so the value head stays a clean win-probability
estimator for the search layer (search.py).

Fresh model by default (no inherited rush prior). Use --warm-start to continue
from a checkpoint instead.

Usage:
  python -m DuckChess_Game.SBThree.train_peter_v2 --hours 24
  python -m DuckChess_Game.SBThree.train_peter_v2 --steps 3000 --n-envs 2   # smoke test
  python -m DuckChess_Game.SBThree.train_peter_v2 --warm-start models/duck_ppo/v2/v2_latest.zip

Monitor:
  tensorboard --logdir tensorboard_logs/v2/
  Get-Content logs/v2_progress.csv -Tail 10 -Wait
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
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

from DuckChess_Game.SBThree.duck_env_v2 import PoolEnv

SAVE_DIR = os.path.join("models", "duck_ppo", "v2")
CSV_PATH = os.path.join("logs", "v2_progress.csv")
# Old-generation models used to seed the self-play slots until v2 has its own
# checkpoints: the new model must learn to DEFEND against the king rush.
HIST_SEEDS = [
    "models/duck_ppo/strong/strong_final.zip",
    "models/duck_ppo/real/real_final.zip",
]

OUTCOMES = ("win", "loss", "draw")


def make_env(rank: int, random_start_prob: float):
    def _init():
        hist = [p for p in HIST_SEEDS if os.path.exists(p)]
        return Monitor(PoolEnv(
            env_index=rank,
            random_start_prob=random_start_prob,
            hist_seed_paths=hist or None,
        ))
    return _init


class V2Callback(BaseCallback):
    """Checkpoints + CSV progress (per-opponent W/L/D, entropy) + league refresh."""

    def __init__(self, hours, save_dir, ckpt_every, csv_path, log_every=10_000):
        super().__init__()
        self.deadline = time.time() + hours * 3600.0
        self.save_dir = save_dir
        self.ckpt_every = ckpt_every
        self.csv_path = csv_path
        self.log_every = log_every
        self.start = time.time()
        self.last_latest = time.time()
        self.version = 0
        self.next_log = log_every
        # tally[opponent][outcome] since the last CSV row
        self.tally: dict = {}

    @staticmethod
    def _atomic_save(model, path: str) -> None:
        tmp = path + ".tmp"
        model.save(tmp)
        os.replace(tmp, path)

    def _init_callback(self) -> None:
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="") as f:
                csv.writer(f).writerow([
                    "timestamp", "steps", "elapsed_s", "steps_per_s",
                    "ep_rew_mean", "ep_len_mean", "entropy_loss",
                    "opponent_wld",  # name:w/l/d joined by ;
                ])

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            if "outcome" in info:
                opp = info.get("opponent", "?")
                row = self.tally.setdefault(opp, {o: 0 for o in OUTCOMES})
                row[info["outcome"]] += 1

        now = time.time()

        if self.num_timesteps >= self.next_log:
            self.next_log += self.log_every
            self._write_csv_row(now)

        if self.num_timesteps - self.version * self.ckpt_every >= self.ckpt_every:
            self.version += 1
            latest = os.path.join(self.save_dir, "v2_latest.zip")
            self._atomic_save(self.model, os.path.join(self.save_dir, f"v2_v{self.version}.zip"))
            self._atomic_save(self.model, latest)
            self.last_latest = now
            self._refresh_league(latest)
            fps = self.num_timesteps / max(1e-9, now - self.start)
            print(f"[v2] step={self.num_timesteps:,} v{self.version} | "
                  f"{(now - self.start) / 3600:.2f}h | {fps:.0f} steps/s", flush=True)
        elif now - self.last_latest > 600:
            self._atomic_save(self.model, os.path.join(self.save_dir, "v2_latest.zip"))
            self.last_latest = now

        if now >= self.deadline:
            print(f"[v2] time budget reached ({(now - self.start) / 3600:.2f}h, "
                  f"{self.num_timesteps:,} steps). stopping.", flush=True)
            return False
        return True

    def _refresh_league(self, latest_path: str) -> None:
        """Point self-play slots at the new latest + a random older v2 checkpoint."""
        # Old-generation rush models stay in the pool forever — defending
        # against the king rush is a skill the new model must keep.
        hist_pool = sorted(glob.glob(os.path.join(self.save_dir, "v2_v*.zip")))
        hist_pool += [p for p in HIST_SEEDS if os.path.exists(p)]
        hist = str(np.random.choice(hist_pool)) if hist_pool else None
        try:
            self.training_env.env_method("set_opponents", latest_path, hist)
        except Exception as exc:
            print(f"[v2] league refresh failed: {exc!r}", flush=True)

    def _write_csv_row(self, now: float) -> None:
        buf = self.model.ep_info_buffer
        rew = float(np.mean([e["r"] for e in buf])) if buf else float("nan")
        length = float(np.mean([e["l"] for e in buf])) if buf else float("nan")
        ent = self.model.logger.name_to_value.get("train/entropy_loss", float("nan"))
        wld = ";".join(
            f"{opp}:{t['win']}/{t['loss']}/{t['draw']}"
            for opp, t in sorted(self.tally.items())
        )
        with open(self.csv_path, "a", newline="") as f:
            csv.writer(f).writerow([
                int(now), self.num_timesteps, round(now - self.start, 1),
                round(self.num_timesteps / max(1e-9, now - self.start), 2),
                round(rew, 4), round(length, 1), round(float(ent), 4), wld,
            ])
        self.tally = {}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=float, default=24.0)
    p.add_argument("--steps", type=int, default=1_000_000_000,
                   help="Step bound (default: unbounded, --hours stops the run)")
    p.add_argument("--n-envs", type=int, default=8)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--ent-coef", type=float, default=0.02,
                   help="Higher than v1's 0.01 — exploit policies are low-entropy")
    p.add_argument("--ckpt-every", type=int, default=100_000)
    p.add_argument("--random-start-prob", type=float, default=0.4)
    p.add_argument("--log-every", type=int, default=10_000)
    p.add_argument("--warm-start", type=str, default=None,
                   help="Continue from this checkpoint instead of a fresh model")
    args = p.parse_args()

    os.makedirs(SAVE_DIR, exist_ok=True)

    print(f"=== v2 TRAINING: pool opponents, random starts (p={args.random_start_prob}), "
          f"sparse reward | {args.hours}h / {args.steps:,} steps | {args.n_envs} envs ===",
          flush=True)

    vec = SubprocVecEnv([make_env(i, args.random_start_prob) for i in range(args.n_envs)])

    if args.warm_start:
        print(f"[v2] warm-starting from {args.warm_start}", flush=True)
        model = MaskablePPO.load(
            args.warm_start, env=vec,
            tensorboard_log="./tensorboard_logs/v2/",
            custom_objects={"learning_rate": args.lr, "ent_coef": args.ent_coef,
                            "target_kl": 0.05},
        )
    else:
        print("[v2] FRESH model (no inherited king-rush prior)", flush=True)
        model = MaskablePPO(
            "MlpPolicy", vec,
            learning_rate=args.lr, ent_coef=args.ent_coef, target_kl=0.05,
            n_steps=512, batch_size=256, verbose=1,
            tensorboard_log="./tensorboard_logs/v2/",
        )

    cb = V2Callback(args.hours, SAVE_DIR, args.ckpt_every, CSV_PATH,
                    log_every=args.log_every)
    model.learn(total_timesteps=args.steps, callback=cb,
                tb_log_name="v2", reset_num_timesteps=True)

    final = os.path.join(SAVE_DIR, "v2_final.zip")
    model.save(final)
    vec.close()
    print(f"[v2] saved -> {final}", flush=True)
    print("[v2] next: python -m DuckChess_Game.SBThree.eval_anchors --model "
          f"{final}", flush=True)


if __name__ == "__main__":
    main()
