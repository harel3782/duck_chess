#!/usr/bin/env python
"""
eval_vs_peter.py — Ground-truth strength evaluation for Duck Chess models.

Plays a saved MaskablePPO checkpoint against the local Peter engine for a fixed
number of games and reports Win / Loss / Draw counts and a score. This is the
metric we actually trust for "is the model good", because the training logs
never recorded ``ep_rew_mean`` (no Monitor wrapper was used).

Replaces eval_peter_save_replays.py — use --save-replays to save game replays.

Usage:
  # Evaluate one checkpoint, 40 games vs Peter depth 2
  python -m DuckChess_Game.SBThree.eval_vs_peter \
      --model "models/duck_ppo/peter_local/peter_local_v20.zip" \
      --games 40 --depth 2

  # Compare several checkpoints (sweep) at depth 2
  python -m DuckChess_Game.SBThree.eval_vs_peter \
      --sweep "models/duck_ppo/peter_local/peter_local_v*.zip" \
      --games 20 --depth 2

  # Evaluate at multiple depths with replay saving (replaces eval_peter_save_replays.py)
  python -m DuckChess_Game.SBThree.eval_vs_peter \
      --model models/duck_ppo/real/real_final.zip \
      --depths 2 3 --games 8 --save-replays

The agent's colour is randomised each game (matches training), and Peter is
re-seeded per game so results are not a single deterministic line.
"""
from __future__ import annotations

import os
import sys
import glob
import time
import argparse
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch

torch.distributions.Distribution.set_default_validate_args(False)

from sb3_contrib import MaskablePPO

from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config


def evaluate(model_path: str, games: int = 40, depth: int = 2,
             deterministic: bool = False, verbose: bool = True,
             save_replays: bool = False) -> dict:
    """Play `games` games of `model_path` vs Peter@`depth`. Returns a result dict."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(model_path)

    model = MaskablePPO.load(model_path, device="cpu")
    if save_replays:
        config = make_peter_config(depth=depth, stage_name=f"eval_d{depth}", replay_every=1)
        env = PeterLocalEnv(config, env_index=0)
    else:
        env = PeterLocalEnv(make_peter_config(depth=depth), env_index=1)

    wins = losses = draws = 0
    t0 = time.time()

    for g in range(games):
        obs, _ = env.reset()
        terminated = truncated = False
        while not (terminated or truncated):
            masks = env.action_masks()
            if not np.any(masks):
                break
            action, _ = model.predict(obs, action_masks=masks,
                                      deterministic=deterministic)
            obs, reward, terminated, truncated, _ = env.step(int(action))

        winner = getattr(env.engine, "winner", None)
        lc = env.learning_color
        if winner == "draw" or winner is None:
            draws += 1
            tag = "draw"
        elif winner == lc:
            wins += 1
            tag = "WIN"
        else:
            losses += 1
            tag = "loss"
        if verbose:
            print(f"  game {g + 1:>3}/{games}  agent={lc}  -> {tag}")

    dt = time.time() - t0
    score = (wins + 0.5 * draws) / games if games else 0.0
    result = {
        "model": os.path.basename(model_path),
        "games": games,
        "depth": depth,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "score": score,
        "win_rate": wins / games if games else 0.0,
        "seconds": dt,
    }
    if verbose:
        print(f"\n{result['model']}  vs Peter d{depth}  ({games} games, {dt:.0f}s)")
        print(f"  W/L/D = {wins}/{losses}/{draws}   "
              f"win_rate={result['win_rate']:.1%}   score={score:.3f}")
    return result


def main():
    p = argparse.ArgumentParser(description="Evaluate Duck Chess model vs local Peter")
    p.add_argument("--model", help="Path to a single .zip checkpoint")
    p.add_argument("--sweep", help="Glob of checkpoints to compare, e.g. '.../peter_local_v*.zip'")
    p.add_argument("--games", type=int, default=40, help="Games per model (default 40)")
    p.add_argument("--depth", type=int, default=2, help="Peter search depth (default 2)")
    p.add_argument("--depths", nargs="+", type=int, default=None,
                   help="Run eval at multiple depths in one shot, e.g. --depths 2 3")
    p.add_argument("--deterministic", action="store_true",
                   help="Use deterministic (argmax) policy instead of sampling")
    p.add_argument("--save-replays", action="store_true",
                   help="Save game replays to saved_replays/eval_d{depth}/ (replaces eval_peter_save_replays.py)")
    args = p.parse_args()

    if args.sweep:
        paths = sorted(
            glob.glob(args.sweep),
            key=lambda x: int(''.join(ch for ch in os.path.basename(x).split('v')[-1]
                                      if ch.isdigit()) or 0),
        )
        if not paths:
            print(f"No checkpoints matched: {args.sweep}")
            return
        print(f"Sweeping {len(paths)} checkpoints, {args.games} games each vs Peter d{args.depth}\n")
        rows = []
        for path in paths:
            r = evaluate(path, games=args.games, depth=args.depth,
                         deterministic=args.deterministic, verbose=False,
                         save_replays=args.save_replays)
            rows.append(r)
            print(f"  {r['model']:<28}  W/L/D={r['wins']:>3}/{r['losses']:>3}/{r['draws']:>3}"
                  f"   score={r['score']:.3f}   win={r['win_rate']:.1%}")
        rows.sort(key=lambda r: r["score"], reverse=True)
        print("\n=== Ranked by score ===")
        for r in rows:
            print(f"  {r['score']:.3f}  {r['model']}")
        print(f"\nBEST: {rows[0]['model']}  (score {rows[0]['score']:.3f})")
        return

    if args.model:
        depths = args.depths if args.depths else [args.depth]
        all_results = []
        for d in depths:
            r = evaluate(args.model, games=args.games, depth=d,
                         deterministic=args.deterministic, verbose=True,
                         save_replays=args.save_replays)
            all_results.append(r)
        if len(depths) > 1:
            print("\n=== Summary ===")
            for r in all_results:
                print(f"  vs Peter d{r['depth']}:  W/L/D={r['wins']:>2}/{r['losses']:>2}/{r['draws']:>2}"
                      f"   score={r['score']:.3f}")
        return

    p.print_help()


if __name__ == "__main__":
    main()
