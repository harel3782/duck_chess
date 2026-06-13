#!/usr/bin/env python
"""
gen_value_data.py — generate (position -> game outcome) data for value distillation.

The v2 policy is strong (95% vs Peter d2) but its PPO value head is a poor
positional evaluator, so search.py (which uses it as the leaf evaluator) HURTS
instead of helping (see PLAN_V2.md Step 6). This script collects supervised
targets to retrain the value head:

  * play the raw v2 policy against the local Peter engine (mixed depths),
  * record the observation at the start of EVERY full turn (move_piece phase),
    for BOTH colors, tagged with whose turn it is,
  * label each with the eventual game result from THAT side's perspective
    (+1 win, -1 loss, 0 draw) — the standard AlphaZero-style Monte-Carlo value
    target.

This matches exactly how search queries the value head: at move_piece-phase
leaves, from the side-to-move's perspective. The duck-phase states are not
recorded — search uses the policy (not the value) to pick duck candidates.

Output: an .npz with obs (N,19,8,8) float32 and z (N,) float32 in [-1,1].

Usage:
  python -m DuckChess_Game.SBThree.gen_value_data --games 400 --out data/value_v2.npz
  python -m DuckChess_Game.SBThree.gen_value_data --games 50 --depths 2 --out data/smoke.npz
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

from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine
from DuckChess_Game.SBThree.base.mask_strategy import ForcedKingCaptureMask
from DuckChess_Game.SBThree.peter_local import PeterLocalOpponent

MOVE_CAP = 400  # half-moves; matches the 50-move-rule horizon with margin
_MASK = ForcedKingCaptureMask()  # MUST match eval/training — forces king captures


def play_one(model, opponent: PeterLocalOpponent, learner_color: str, rng):
    """Play one game (raw policy vs Peter), return list of (obs, side_to_move)."""
    engine = _HeadlessEngine()
    engine.reset_game_state()
    opponent.reset()
    records = []
    half = 0
    while not getattr(engine, "game_over", False) and half < MOVE_CAP:
        if engine.phase == "move_piece":
            records.append((engine._get_obs().copy(), engine.turn))

        masks = _MASK.get_masks(engine)
        if not np.any(masks):
            break

        is_duck = engine.phase == "move_duck"
        if engine.turn == learner_color:
            action, _ = model.predict(engine._get_obs(), action_masks=masks,
                                      deterministic=False)
            action = int(action)
        else:
            action = opponent.get_action(engine, masks)

        start, end = engine._decode_move(action)
        if engine.phase == "move_piece":
            engine.execute_move(start, end, animated=False)
        else:
            engine.place_duck(end, animated=False)
        opponent.mirror_action(action, is_duck_phase=is_duck)
        half += 1

    winner = getattr(engine, "winner", None)
    out = []
    for obs, side in records:
        if winner in (None, "draw"):
            z = 0.0
        else:
            z = 1.0 if side == winner else -1.0
        out.append((obs, z))
    return out, winner, learner_color


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="models/duck_ppo/v2/v2_final.zip")
    p.add_argument("--games", type=int, default=400)
    p.add_argument("--depths", type=int, nargs="+", default=[2, 3],
                   help="Peter depths to cycle through across games")
    p.add_argument("--out", default="data/value_v2.npz")
    p.add_argument("--seed", type=int, default=12345)
    args = p.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    model = MaskablePPO.load(args.model, device="cpu")
    rng = np.random.default_rng(args.seed)

    # One opponent object per depth (each holds its own Peter engine).
    opps = {d: PeterLocalOpponent(depth=d, seed=args.seed + d) for d in args.depths}

    all_obs, all_z = [], []
    wld = {"w": 0, "l": 0, "d": 0}
    t0 = time.time()
    for g in range(args.games):
        depth = args.depths[g % len(args.depths)]
        learner = "w" if (g % 2 == 0) else "b"
        recs, winner, lc = play_one(model, opps[depth], learner, rng)
        for obs, z in recs:
            all_obs.append(obs)
            all_z.append(z)
        if winner in (None, "draw"):
            wld["d"] += 1
        elif winner == lc:
            wld["w"] += 1
        else:
            wld["l"] += 1
        if (g + 1) % 20 == 0 or g == args.games - 1:
            n = len(all_z)
            print(f"  game {g + 1}/{args.games}  samples={n}  "
                  f"W/L/D={wld['w']}/{wld['l']}/{wld['d']}  "
                  f"({time.time() - t0:.0f}s)", flush=True)

    obs_arr = np.asarray(all_obs, dtype=np.float32)
    z_arr = np.asarray(all_z, dtype=np.float32)
    np.savez_compressed(args.out, obs=obs_arr, z=z_arr)
    print(f"\nsaved {len(z_arr)} samples -> {args.out}", flush=True)
    print(f"  z balance: win={np.mean(z_arr > 0):.2%}  "
          f"loss={np.mean(z_arr < 0):.2%}  draw={np.mean(z_arr == 0):.2%}",
          flush=True)


if __name__ == "__main__":
    main()
