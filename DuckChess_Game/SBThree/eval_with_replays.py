#!/usr/bin/env python
"""
eval_with_replays.py — Evaluate a Duck Chess model and save game replays.

Plays games against Peter engine at specified depths and saves all games
to the replay directory for inspection.

Usage:
  python -m DuckChess_Game.SBThree.eval_with_replays \
      --model "models/duck_ppo/real/real_final.zip" \
      --games 16 --depth2-games 8 --depth3-games 8
"""
from __future__ import annotations

import os
import sys
import time
import argparse
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch

torch.distributions.Distribution.set_default_validate_args(False)

from sb3_contrib import MaskablePPO

from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config


def evaluate_with_replays(
    model_path: str,
    games_per_depth: dict = None,
    deterministic: bool = False,
    verbose: bool = True,
) -> None:
    """
    Play games and save replays.

    games_per_depth: e.g. {2: 8, 3: 8}
    """
    if games_per_depth is None:
        games_per_depth = {2: 8, 3: 8}

    if not os.path.exists(model_path):
        raise FileNotFoundError(model_path)

    model = MaskablePPO.load(model_path, device="cpu")

    all_results = {}

    for depth, games in games_per_depth.items():
        print(f"\n{'='*60}")
        print(f"Evaluating vs Peter depth-{depth} ({games} games)")
        print(f"{'='*60}\n")

        # Create config with replay saving enabled
        config = make_peter_config(
            depth=depth,
            stage_name=f"real_eval_d{depth}",
            replay_every=1,  # Save every game
        )
        env = PeterLocalEnv(config, env_index=0)  # must be 0 — replay_chief_only skips env_index!=0

        wins = losses = draws = 0
        t0 = time.time()

        for g in range(games):
            obs, _ = env.reset()
            terminated = truncated = False
            while not (terminated or truncated):
                masks = env.action_masks()
                if not np.any(masks):
                    break
                action, _ = model.predict(
                    obs, action_masks=masks, deterministic=deterministic
                )
                obs, reward, terminated, truncated, _ = env.step(int(action))

            winner = getattr(env.engine, "winner", None)
            lc = env.learning_color
            if winner == "draw" or winner is None:
                draws += 1
                tag = "DRAW"
            elif winner == lc:
                wins += 1
                tag = "WIN "
            else:
                losses += 1
                tag = "LOSS"

            if verbose:
                print(f"  game {g + 1:>3}/{games}  agent={lc}  -> {tag}")

        dt = time.time() - t0
        score = (wins + 0.5 * draws) / games if games else 0.0

        all_results[depth] = {
            "depth": depth,
            "games": games,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "score": score,
            "seconds": dt,
        }

        print(f"\n  Results: W/L/D = {wins}/{losses}/{draws}   score={score:.3f}   ({dt:.1f}s)")
        print(f"  Replays saved to: {config.replay_dir}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for depth in sorted(all_results.keys()):
        r = all_results[depth]
        print(f"  vs Peter d{depth}:  W/L/D={r['wins']:>2}/{r['losses']:>2}/{r['draws']:>2}   score={r['score']:.3f}")

    print(f"\n✓ Model: {os.path.basename(model_path)}")
    print(f"✓ Total games: {sum(r['games'] for r in all_results.values())}")
    print(f"\n📁 Inspect replays in:")
    print(f"   saved_replays/real_eval_d2/")
    print(f"   saved_replays/real_eval_d3/")


def main():
    p = argparse.ArgumentParser(
        description="Evaluate Duck Chess model vs Peter (with replay saving)"
    )
    p.add_argument(
        "--model",
        default="models/duck_ppo/real/real_final.zip",
        help="Path to model checkpoint",
    )
    p.add_argument(
        "--games",
        type=int,
        default=8,
        help="Total games per depth (default 8)",
    )
    p.add_argument(
        "--depth2-games",
        type=int,
        help="Override: games vs depth-2 (default: --games value)",
    )
    p.add_argument(
        "--depth3-games",
        type=int,
        help="Override: games vs depth-3 (default: --games value)",
    )
    p.add_argument(
        "--deterministic",
        action="store_true",
        help="Use deterministic policy",
    )
    args = p.parse_args()

    games_per_depth = {
        2: args.depth2_games if args.depth2_games is not None else args.games,
        3: args.depth3_games if args.depth3_games is not None else args.games,
    }

    evaluate_with_replays(
        args.model,
        games_per_depth=games_per_depth,
        deterministic=args.deterministic,
    )


if __name__ == "__main__":
    main()
