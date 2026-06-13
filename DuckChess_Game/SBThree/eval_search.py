#!/usr/bin/env python
"""
eval_search.py — evaluate a checkpoint WITH n-step lookahead (search.py) vs Peter.

Compares against eval_vs_peter.py (raw policy) to measure what the search layer
adds. The agent plays full turns chosen by DuckSearch: piece move + duck move,
both found by alpha-beta over the policy-pruned tree.

Usage:
  # quick sanity benchmark (no games): timing + node counts on the start position
  python -m DuckChess_Game.SBThree.eval_search --model <ckpt> --bench

  # 10 games vs Peter depth 3, searching 2 full turns ahead
  python -m DuckChess_Game.SBThree.eval_search --model <ckpt> --games 10 \
      --peter-depth 3 --depth 2
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

from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config
from DuckChess_Game.SBThree.search import DuckSearch


def bench(model_path: str, depth: int, piece_topk: int, duck_topk: int,
          leaf_eval: str = "value") -> None:
    from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine

    model = MaskablePPO.load(model_path, device="cpu")
    searcher = DuckSearch(model, depth=depth, piece_topk=piece_topk,
                          duck_topk=duck_topk, leaf_eval=leaf_eval)
    engine = _HeadlessEngine()

    for turn in range(3):
        t0 = time.time()
        piece_a, duck_a = searcher.choose_turn(engine)
        dt = time.time() - t0
        print(f"turn {turn + 1}: piece={piece_a} duck={duck_a} | "
              f"{dt:.2f}s | {searcher.nodes} nodes | {searcher.nn_calls} NN calls")
        if piece_a is None:
            break
        start, end = engine._decode_move(piece_a)
        engine.execute_move(start, end, animated=False)
        if getattr(engine, "game_over", False) or duck_a is None:
            break
        _, duck_to = engine._decode_move(duck_a)
        engine.place_duck(duck_to, animated=False)
        # opponent: random reply so the bench covers several positions
        for _ in range(2):
            if getattr(engine, "game_over", False):
                break
            masks = engine.action_masks()
            valid = np.where(masks)[0]
            a = int(np.random.choice(valid))
            s, e = engine._decode_move(a)
            if engine.phase == "move_piece":
                engine.execute_move(s, e, animated=False)
            else:
                engine.place_duck(e, animated=False)


def evaluate(model_path: str, games: int, peter_depth: int, depth: int,
             piece_topk: int, duck_topk: int, leaf_eval: str = "value",
             mode: str = "best", veto_margin: float = 0.2,
             engine_kind: str = "search", sims: int = 200, c_puct: float = 1.5) -> dict:
    model = MaskablePPO.load(model_path, device="cpu")
    if engine_kind == "mcts":
        from DuckChess_Game.SBThree.mcts import DuckMCTS
        searcher = DuckMCTS(model, sims=sims, c_puct=c_puct,
                            piece_topk=piece_topk, duck_topk=duck_topk)
        label = f"mcts(sims={sims}, c_puct={c_puct}, topk={piece_topk}/{duck_topk})"
    else:
        searcher = DuckSearch(model, depth=depth, piece_topk=piece_topk,
                              duck_topk=duck_topk, leaf_eval=leaf_eval,
                              mode=mode, veto_margin=veto_margin)
        label = f"search(depth={depth}, topk={piece_topk}/{duck_topk}, leaf={leaf_eval}, mode={mode})"
    env = PeterLocalEnv(make_peter_config(depth=peter_depth), env_index=1)

    wins = losses = draws = 0
    move_times = []
    t0 = time.time()

    for g in range(games):
        obs, _ = env.reset()
        terminated = False
        while not terminated:
            if not np.any(env.action_masks()):
                break
            tm = time.time()
            piece_a, duck_a = searcher.choose_turn(env.engine)
            move_times.append(time.time() - tm)
            if piece_a is None:
                break
            obs, _, terminated, _, _ = env.step(int(piece_a))
            if terminated or duck_a is None:
                break
            obs, _, terminated, _, _ = env.step(int(duck_a))

        winner = getattr(env.engine, "winner", None)
        lc = env.learning_color
        if winner in (None, "draw"):
            draws += 1
            tag = "draw"
        elif winner == lc:
            wins += 1
            tag = "WIN"
        else:
            losses += 1
            tag = "loss"
        print(f"  game {g + 1:>3}/{games}  agent={lc}  -> {tag}  "
              f"(avg {np.mean(move_times):.2f}s/turn)", flush=True)

    dt = time.time() - t0
    score = (wins + 0.5 * draws) / games if games else 0.0
    print(f"\n{os.path.basename(model_path)} + {label}  "
          f"vs Peter d{peter_depth}  ({games} games, {dt:.0f}s)")
    print(f"  W/L/D = {wins}/{losses}/{draws}   win_rate={wins / games:.1%}   "
          f"score={score:.3f}   avg_turn={np.mean(move_times):.2f}s")
    return {"wins": wins, "losses": losses, "draws": draws, "score": score}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--bench", action="store_true", help="Timing sanity check only")
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--peter-depth", type=int, default=2)
    p.add_argument("--depth", type=int, default=2,
                   help="Search depth in FULL turns (each = piece + duck)")
    p.add_argument("--piece-topk", type=int, default=8)
    p.add_argument("--duck-topk", type=int, default=4)
    p.add_argument("--leaf-eval", default="value",
                   choices=("value", "material", "mix"),
                   help="Leaf evaluator: 'value' for sparse-reward models (v2), "
                        "'material' or 'mix' for dense-reward-era checkpoints")
    p.add_argument("--mode", default="best", choices=("best", "veto", "sample-veto"),
                   help="'veto' = play the policy's move unless search proves "
                        "it loses; 'best' = always play search's best macro")
    p.add_argument("--veto-margin", type=float, default=0.2)
    p.add_argument("--engine", default="search", choices=("search", "mcts"))
    p.add_argument("--sims", type=int, default=200, help="MCTS simulations per move")
    p.add_argument("--c-puct", type=float, default=1.5)
    args = p.parse_args()

    if args.bench:
        bench(args.model, args.depth, args.piece_topk, args.duck_topk, args.leaf_eval)
    else:
        evaluate(args.model, args.games, args.peter_depth, args.depth,
                 args.piece_topk, args.duck_topk, args.leaf_eval,
                 args.mode, args.veto_margin,
                 engine_kind=args.engine, sims=args.sims, c_puct=args.c_puct)


if __name__ == "__main__":
    main()
