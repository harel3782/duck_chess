#!/usr/bin/env python
"""
run_exit.py — Expert-Iteration controller: the loop that builds the best model.

Each iteration:
  1. GENERATE  MCTS games with the current model (gen_mcts_data): a self-play
     fraction (general improvement) + a fraction vs Peter at a MIX of depths —
     d1 to drill king-rush DEFENCE (the measured weakness of strong models) and
     d2 for decisive, winnable conversion signal.
  2. TRAIN     both heads on a replay window of recent iterations (train_exit).
  3. EVALUATE  the new model WITH MCTS vs Peter d1 (rush), d2 (proper), d3 (wall).
  4. ADVANCE   current <- new model (AlphaZero-style always-accept), while keeping
     a guarded copy of the best model by (d1+d2 robustness, then d3) so a late
     regression can never lose the best one.

Why d1+d2: a human is beaten by raw strength (d2) but a human ATTACKS THE KING,
which is the d1-style rush. The best human opponent must do both — so the guard
maximizes rush-robustness + dominance, not just the d3 wall.

Usage (much-better run from the strong base, unattended):
  python -m DuckChess_Game.SBThree.run_exit \
      --base models/duck_ppo/strong/strong_final.zip \
      --out-dir models/duck_ppo/exit2 --iters 8 --games 500 --sims 300 \
      --workers 8 --peter-frac 0.40 --peter-depths 1 2 --eval-games 16 --eval-sims 200

Smoke (proves the loop end-to-end; the model won't be good):
  python -m DuckChess_Game.SBThree.run_exit --base models/duck_ppo/v2/v2_value.zip \
      --out-dir models/duck_ppo/exit_smoke --iters 1 --games 4 --sims 20 \
      --workers 2 --peter-frac 0.5 --peter-depths 1 2 --eval-games 2 --eval-sims 20 --epochs 2
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import time
import warnings

warnings.filterwarnings("ignore")

import torch

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.gen_mcts_data import generate
from DuckChess_Game.SBThree.train_exit import train_exit
from DuckChess_Game.SBThree.eval_search import evaluate


def _csv_init(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow([
                "iter", "timestamp", "samples",
                "d1_w", "d1_l", "d1_d", "d1_score",
                "d2_w", "d2_l", "d2_d", "d2_score",
                "d3_w", "d3_l", "d3_d", "d3_score",
                "gen_s", "train_s", "eval_s", "accepted_best",
            ])


def run(base, out_dir, *, iters=8, games=500, sims=300, workers=8,
        peter_frac=0.40, peter_depths=(1, 2), window=4, epochs=10, lr=1e-4,
        eval_games=16, eval_sims=200, piece_topk=8, duck_topk=6, seed=0):
    os.makedirs(out_dir, exist_ok=True)
    data_dir = os.path.join(out_dir, "data")
    csv_path = os.path.join(out_dir, "exit_progress.csv")
    _csv_init(csv_path)

    current = base
    data_window = []
    best_path = os.path.join(out_dir, "exit_best.zip")
    best_key = (-1.0, -1.0)   # (d1+d2 robustness, d3): maximize human-strength, tiebreak d3

    print(f"=== ExIt | base={os.path.basename(base)} | {iters} iters | "
          f"{games} games/iter (peter_frac={peter_frac}, depths={tuple(peter_depths)}) | "
          f"sims={sims} | window={window} files ===", flush=True)

    for it in range(1, iters + 1):
        t_it = time.time()
        peter_games = int(round(games * peter_frac))
        self_games = games - peter_games

        # ---- 1. generate ------------------------------------------------ #
        t0 = time.time()
        files_this = []
        if self_games > 0:
            files_this.append(generate(
                current, self_games, sims, workers,
                os.path.join(data_dir, f"it{it}_self.npz"),
                opponent="self", seed=seed + it * 1000))
        if peter_games > 0:
            files_this.append(generate(
                current, peter_games, sims, workers,
                os.path.join(data_dir, f"it{it}_peter.npz"),
                opponent="peter", peter_depths=tuple(peter_depths),
                seed=seed + it * 1000 + 7))
        gen_s = time.time() - t0

        data_window.extend(files_this)
        data_window = data_window[-window:]        # sliding replay window

        # ---- 2. train --------------------------------------------------- #
        t0 = time.time()
        model_it = os.path.join(out_dir, f"exit_v{it}.zip")
        train_exit(current, data_window, model_it, epochs=epochs, lr=lr,
                   seed=seed + it)
        train_s = time.time() - t0

        # ---- 3. evaluate (with MCTS) ------------------------------------ #
        t0 = time.time()
        print(f"[run_exit] iter {it}: eval vs Peter d1 (rush) ...", flush=True)
        r1 = evaluate(model_it, eval_games, 1, 2, piece_topk, duck_topk,
                      engine_kind="mcts", sims=eval_sims)
        print(f"[run_exit] iter {it}: eval vs Peter d2 ...", flush=True)
        r2 = evaluate(model_it, eval_games, 2, 2, piece_topk, duck_topk,
                      engine_kind="mcts", sims=eval_sims)
        print(f"[run_exit] iter {it}: eval vs Peter d3 ...", flush=True)
        r3 = evaluate(model_it, eval_games, 3, 2, piece_topk, duck_topk,
                      engine_kind="mcts", sims=eval_sims)
        eval_s = time.time() - t0

        # ---- 4. advance + guard best ------------------------------------ #
        current = model_it                          # always-accept
        # Human-relevant strength: rush-robustness (d1) + dominance (d2); tiebreak d3.
        key = (round(r1["score"] + r2["score"], 3), r3["score"])
        is_best = key > best_key
        if is_best:
            best_key = key
            shutil.copyfile(model_it, best_path)

        # count samples in the most recent data file(s)
        import numpy as np
        samples = sum(int(np.load(f)["z"].shape[0]) for f in files_this)

        with open(csv_path, "a", newline="") as f:
            csv.writer(f).writerow([
                it, int(time.time()), samples,
                r1["wins"], r1["losses"], r1["draws"], round(r1["score"], 3),
                r2["wins"], r2["losses"], r2["draws"], round(r2["score"], 3),
                r3["wins"], r3["losses"], r3["draws"], round(r3["score"], 3),
                round(gen_s, 1), round(train_s, 1), round(eval_s, 1), int(is_best),
            ])
        print(f"[run_exit] iter {it} DONE in {(time.time() - t_it) / 60:.1f} min | "
              f"d1 {r1['wins']}/{r1['losses']}/{r1['draws']} ({r1['score']:.2f}) | "
              f"d2 {r2['wins']}/{r2['losses']}/{r2['draws']} ({r2['score']:.2f}) | "
              f"d3 {r3['wins']}/{r3['losses']}/{r3['draws']} ({r3['score']:.2f}) | "
              f"{'NEW BEST' if is_best else 'kept prior best'}", flush=True)

    print(f"\n=== ExIt finished. Best (d1+d2, d3)={best_key} -> {best_path} ===", flush=True)
    return best_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--iters", type=int, default=8)
    p.add_argument("--games", type=int, default=500)
    p.add_argument("--sims", type=int, default=300)
    p.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    p.add_argument("--peter-frac", type=float, default=0.40,
                   help="fraction of generated games played vs Peter")
    p.add_argument("--peter-depths", type=int, nargs="+", default=[1, 2],
                   help="Peter depths to cycle in generation (d1=rush defence, d2=conversion)")
    p.add_argument("--window", type=int, default=4, help="replay window (data files)")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--eval-games", type=int, default=16)
    p.add_argument("--eval-sims", type=int, default=200)
    p.add_argument("--piece-topk", type=int, default=8)
    p.add_argument("--duck-topk", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    run(args.base, args.out_dir, iters=args.iters, games=args.games, sims=args.sims,
        workers=args.workers, peter_frac=args.peter_frac, peter_depths=tuple(args.peter_depths),
        window=args.window, epochs=args.epochs, lr=args.lr,
        eval_games=args.eval_games, eval_sims=args.eval_sims,
        piece_topk=args.piece_topk, duck_topk=args.duck_topk, seed=args.seed)


if __name__ == "__main__":
    main()
