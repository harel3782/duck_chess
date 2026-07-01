#!/usr/bin/env python
"""
train_real.py — corrective run to break the king-rush exploit and teach real positional play.

Replaces train_real_logged.py. For the old 1-hour continuation with draw=0.1:
  python -m DuckChess_Game.SBThree.train_real \
      --resume models/duck_ppo/real/real_final.zip --hours 1 --draw 0.1

Diagnosis (proven, not assumed): the existing models win only via a ~4-move
knight-rush at the enemy king. It works vs shallow Peter depth-2 and other RL
models, but loses 0/N to Peter depth-3 and to any human; when the rush is
blocked the policy flails (shuffles pieces) and loses.

Design choices, each tied to a finding:
  * Opponent = pure Peter depth-3. Depth-3 defends its king, so the rush fails and
    the model is forced to find something better. (SubprocVecEnv is synchronous, so
    mixing in faster depth-2 envs would NOT add steps — the batch is gated by the
    slowest env regardless — it would only dilute the signal. So: pure depth-3.)
  * DENSE shaped reward. Sparse win/loss vs an opponent you never beat is a flat
    -1 with no gradient (this is why the 1h sparse probe's ep_rew_mean sat at -1
    and nothing changed). The shaped reward rewards development, king safety,
    material, mobility and duck-blocking so the model gets a learning signal on
    every move even while still losing.
  * step_penalty = 0 and king_push_bonus = 0 — both reward the fast king-hunt, so
    they are OFF. draw = +0.1 so surviving is strictly better than suiciding.
  * Warm-start strong_final + higher entropy to pry the policy off its one trick.

Time-bounded to --hours (default 14). Checkpoints to models/duck_ppo/real/.
Does NOT touch strong_final.zip. Evaluates vs depth-2 AND depth-3 before/after.

Honest expectation: ~11 fps -> ~14h is only ~0.5M steps. The exploit took millions
of steps to form, so this may only START to break it. The signals to watch:
survival length vs depth-3 going UP, and games vs depth-2 getting LONGER (rush
replaced by real play).
"""
from __future__ import annotations

import os
import time
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

from DuckChess_Game.SBThree.base.env_base import EnvConfig
from DuckChess_Game.SBThree.base.mask_strategy import ForcedKingCaptureMask
from DuckChess_Game.SBThree.base.reward_calculator import ShapedReward
from DuckChess_Game.SBThree.peter_local import (
    PeterLocalEnv, PeterLocalOpponent, make_peter_config,
)

SAVE_DIR = os.path.join("models", "duck_ppo", "real")
BASE = "models/duck_ppo/strong/strong_final.zip"


def anti_cheese_reward(draw=-0.3):
    return ShapedReward(
        material_weight=0.05,
        loss_multiplier=1.3,
        development_bonus=0.08,
        castling_bonus=0.20,
        defense_weight=0.05,
        mobility_scale=0.004,
        blocking_scale=0.015,
        step_penalty=0.0,
        king_push_bonus=0.01,
        win=1.0, loss=-1.0, draw=draw,
    )


def make_cfg(depth, draw=-0.3):
    return EnvConfig(
        stage_name=f"real_d{depth}",
        opponent=PeterLocalOpponent(depth=depth),
        reward=anti_cheese_reward(draw=draw),
        mask=ForcedKingCaptureMask(),
        randomize_color=True,
        replay_every=1,
        replay_chief_only=False,
    )


def make_env(rank, depth, draw=-0.3):
    def _init():
        return Monitor(PeterLocalEnv(make_cfg(depth, draw=draw), env_index=rank))
    return _init


def eval_vs(model_path, depth, games=8):
    """Return (win_rate, score, avg_halfmoves, (w,l,d)) vs Peter@depth, sampling."""
    model = MaskablePPO.load(model_path, device="cpu")
    env = PeterLocalEnv(make_peter_config(depth=depth), env_index=1)
    w = l = d = 0
    lengths = []
    for _ in range(games):
        obs, _ = env.reset()
        steps = 0
        term = trunc = False
        while not (term or trunc):
            mk = env.action_masks()
            if not np.any(mk):
                break
            a, _ = model.predict(obs, action_masks=mk, deterministic=False)
            obs, r, term, trunc, _ = env.step(int(a))
            steps += 1
        win = getattr(env.engine, "winner", None)
        lc = env.learning_color
        if win == "draw" or win is None:
            d += 1
        elif win == lc:
            w += 1
        else:
            l += 1
        lengths.append(steps)
    return w / games, (w + 0.5 * d) / games, float(np.mean(lengths)), (w, l, d)


class RealCallback(BaseCallback):
    def __init__(self, hours, save_dir, ckpt_every):
        super().__init__()
        self.deadline = time.time() + hours * 3600.0
        self.save_dir = save_dir
        self.ckpt_every = ckpt_every
        self.start = time.time()
        self.last_latest = time.time()
        self.version = 0

    @staticmethod
    def _atomic_save(model, path: str) -> None:
        """Save to a .tmp file then rename — avoids Windows file-lock crash
        when an eval process reads `real_latest.zip` at the same time."""
        tmp = path + ".tmp"
        model.save(tmp)
        os.replace(tmp, path)   # atomic on NTFS

    def _on_step(self) -> bool:
        now = time.time()
        if self.num_timesteps - self.version * self.ckpt_every >= self.ckpt_every:
            self.version += 1
            self._atomic_save(self.model, os.path.join(self.save_dir, f"real_v{self.version}.zip"))
            self._atomic_save(self.model, os.path.join(self.save_dir, "real_latest.zip"))
            self.last_latest = now
            fps = self.num_timesteps / max(1e-9, now - self.start)
            print(f"[real] step={self.num_timesteps:,} v{self.version} | "
                  f"{(now-self.start)/3600:.2f}h | {fps:.0f} steps/s", flush=True)
        elif now - self.last_latest > 600:
            self._atomic_save(self.model, os.path.join(self.save_dir, "real_latest.zip"))
            self.last_latest = now
        if now >= self.deadline:
            print(f"[real] time budget reached ({(now-self.start)/3600:.2f}h, "
                  f"{self.num_timesteps:,} steps). stopping.", flush=True)
            return False
        return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=float, default=14.0)
    p.add_argument("--n-envs", type=int, default=8)
    p.add_argument("--depth", type=int, default=3)
    # Warm-start defaults match the base model (strong_final: lr=1e-4, ent=0.01).
    # The previous 2.5× boost on both was destroying the warm-start in the first
    # few thousand steps. Pass --lr / --ent-coef explicitly if you want a higher
    # value to pry the policy off a local optimum.
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--ent-coef", type=float, default=0.01)
    p.add_argument("--ckpt-every", type=int, default=50_000)
    p.add_argument("--resume", type=str, default=None,
                   help="Resume from this checkpoint instead of BASE (e.g. models/duck_ppo/real/real_v4.zip)")
    p.add_argument("--draw", type=float, default=-0.3,
                   help="Draw reward (default -0.3; use 0.1 to incentivize survival over winning)")
    args = p.parse_args()

    os.makedirs(SAVE_DIR, exist_ok=True)

    start_model = args.resume if args.resume else BASE
    print(f"=== BASELINE ({os.path.basename(start_model)}) ===", flush=True)
    for dep in (2, 3):
        wr, sc, ln, wld = eval_vs(start_model, dep, games=8)
        print(f"  vs d{dep}: win={wr:.0%} score={sc:.3f} avg_len={ln:.0f}hm W/L/D={wld}", flush=True)

    print(f"\n=== TRAINING {args.hours}h vs Peter depth-{args.depth} "
          f"({args.n_envs} envs), DENSE anti-cheese reward ===", flush=True)
    vec = SubprocVecEnv([make_env(i, args.depth, draw=args.draw) for i in range(args.n_envs)])
    model = MaskablePPO.load(
        start_model, env=vec,
        tensorboard_log="./tensorboard_logs/real/",
        custom_objects={"learning_rate": args.lr, "ent_coef": args.ent_coef, "target_kl": 0.06},
    )
    model.learn(total_timesteps=1_000_000_000,
                callback=RealCallback(args.hours, SAVE_DIR, args.ckpt_every),
                tb_log_name="real", reset_num_timesteps=True)
    final = os.path.join(SAVE_DIR, "real_final.zip")
    model.save(final)
    vec.close()
    print(f"[real] saved -> {final}", flush=True)

    print("\n=== AFTER (real_final) ===", flush=True)
    res = {}
    for dep in (2, 3):
        wr, sc, ln, wld = eval_vs(final, dep, games=10)
        res[dep] = (wr, sc, ln, wld)
        print(f"  vs d{dep}: win={wr:.0%} score={sc:.3f} avg_len={ln:.0f}hm W/L/D={wld}", flush=True)

    print("\n================ SUMMARY (vs depth-3 = the real test) ================", flush=True)
    print(f"  Goal signals: survival length UP vs d3, and longer games vs d2 "
          f"(rush replaced by real play).", flush=True)


if __name__ == "__main__":
    main()
