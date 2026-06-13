#!/usr/bin/env python
"""
eval_anchors.py — honest strength evaluation against a FIXED anchor set.

Self-play win rates and training-opponent win rates historically overstated
real strength (the king-rush models "beat" Peter d2 100% and lost to everyone
else). This script plays a checkpoint against a ladder of fixed opponents it
is not being optimized against during the games, and fits a single Elo number
to the results, so checkpoints are comparable across runs and stages.

Anchor ladder (ratings are an arbitrary-but-FIXED internal scale; only
differences between checkpoints matter):
    random      400   uniform random legal moves
    greedy      600   prefers captures
    alphabeta   800   depth-1 material maximizer
    peter_d1   1000   Peter engine, depth 1
    peter_d2   1200   Peter engine, depth 2
    peter_d3   1400   Peter engine, depth 3

Usage:
  python -m DuckChess_Game.SBThree.eval_anchors --model models/duck_ppo/v2/v2_latest.zip
  python -m DuckChess_Game.SBThree.eval_anchors --model <ckpt> --games 20
  python -m DuckChess_Game.SBThree.eval_anchors --model <ckpt> --search-depth 2  # with lookahead
"""
from __future__ import annotations

import argparse
import os
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch

torch.distributions.Distribution.set_default_validate_args(False)

from sb3_contrib import MaskablePPO

from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv, EnvConfig
from DuckChess_Game.SBThree.base.mask_strategy import ForcedKingCaptureMask
from DuckChess_Game.SBThree.base.opponent_strategy import (
    AlphaBetaOpponent, GreedyOpponent, RandomOpponent,
)
from DuckChess_Game.SBThree.base.reward_calculator import TerminalReward
from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config

ANCHORS = [
    ("random",    400),
    ("greedy",    600),
    ("alphabeta", 800),
    ("peter_d1", 1000),
    ("peter_d2", 1200),
    ("peter_d3", 1400),
]


def make_anchor_env(name: str):
    if name.startswith("peter_d"):
        depth = int(name[-1])
        return PeterLocalEnv(make_peter_config(depth=depth, replay_every=0), env_index=1)
    opponent = {
        "random": RandomOpponent,
        "greedy": GreedyOpponent,
        "alphabeta": AlphaBetaOpponent,
    }[name]()
    cfg = EnvConfig(
        stage_name=f"anchor_{name}",
        opponent=opponent,
        reward=TerminalReward(win=1.0, loss=-1.0, draw=0.0),
        mask=ForcedKingCaptureMask(),
        randomize_color=True,
        replay_every=0,
    )
    return BaseDuckChessEnv(cfg, env_index=1)


def play_games(model, env, games: int, searcher=None) -> tuple:
    wins = losses = draws = 0
    for _ in range(games):
        obs, _ = env.reset()
        terminated = False
        while not terminated:
            masks = env.action_masks()
            if not np.any(masks):
                break
            if searcher is not None and env.engine.phase == "move_piece":
                piece_a, duck_a = searcher.choose_turn(env.engine)
                if piece_a is None:
                    break
                obs, _, terminated, _, _ = env.step(int(piece_a))
                if terminated or duck_a is None:
                    break
                obs, _, terminated, _, _ = env.step(int(duck_a))
            else:
                action, _ = model.predict(obs, action_masks=masks, deterministic=False)
                obs, _, terminated, _, _ = env.step(int(action))
        winner = getattr(env.engine, "winner", None)
        if winner in (None, "draw"):
            draws += 1
        elif winner == env.learning_color:
            wins += 1
        else:
            losses += 1
    return wins, losses, draws


def fit_elo(results: dict) -> float:
    """Max-likelihood Elo over the anchor results (grid search, 1-point grid)."""
    ratings = dict(ANCHORS)

    def neg_log_lik(r: float) -> float:
        ll = 0.0
        for name, (w, l, d) in results.items():
            e = 1.0 / (1.0 + 10 ** ((ratings[name] - r) / 400.0))
            e = min(max(e, 1e-9), 1 - 1e-9)
            ll += w * np.log(e) + l * np.log(1 - e) + d * 0.5 * (np.log(e) + np.log(1 - e))
        return -ll

    grid = np.arange(0, 2201, 1.0)
    return float(grid[int(np.argmin([neg_log_lik(r) for r in grid]))])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--games", type=int, default=10, help="Games per anchor")
    p.add_argument("--search-depth", type=int, default=0,
                   help="0 = raw policy; >0 = use DuckSearch with this depth (full turns)")
    p.add_argument("--leaf-eval", default="value", choices=("value", "material", "mix"))
    p.add_argument("--skip", default="", help="Comma-separated anchor names to skip")
    args = p.parse_args()

    model = MaskablePPO.load(args.model, device="cpu")
    searcher = None
    if args.search_depth > 0:
        from DuckChess_Game.SBThree.search import DuckSearch
        searcher = DuckSearch(model, depth=args.search_depth, leaf_eval=args.leaf_eval)

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    tag = f" + search(depth={args.search_depth})" if searcher else " (raw policy)"
    print(f"=== Anchor evaluation: {os.path.basename(args.model)}{tag}, "
          f"{args.games} games/anchor ===", flush=True)

    results = {}
    for name, rating in ANCHORS:
        if name in skip:
            continue
        env = make_anchor_env(name)
        t0 = time.time()
        w, l, d = play_games(model, env, args.games, searcher)
        results[name] = (w, l, d)
        score = (w + 0.5 * d) / args.games
        print(f"  vs {name:<10} (~{rating:>4}) W/L/D = {w:>2}/{l:>2}/{d:>2}  "
              f"score={score:.2f}  ({time.time() - t0:.0f}s)", flush=True)

    elo = fit_elo(results)
    print(f"\n  Anchor Elo: {elo:.0f}", flush=True)
    return results


if __name__ == "__main__":
    main()
