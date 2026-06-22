#!/usr/bin/env python
"""
gen_mcts_data.py — Expert-Iteration data generator (the missing "Step 7b").

Unlike gen_value_data.py (which records only outcomes from RAW-policy play to
retrain the VALUE head), this plays games where the *expert* — AlphaZero MCTS
(mcts.py) using the current model as policy-prior + value-leaf — chooses every
move, and records BOTH:

  * the MCTS visit-count distribution π at each node  (policy target), and
  * the eventual game outcome z from that node's perspective (value target).

Crucially it records π for the DUCK node as well as the piece node, so the
policy learns better duck placement — the second diagnosed exploit. Moves are
SAMPLED from π (temperature) with Dirichlet root noise, so self-play explores
many openings — attacking the opening-repetition exploit at the search level.

train_exit.py then regresses BOTH heads onto (π, z); iterating gen→train→gen is
Expert Iteration, the only identified path at the Peter depth-3 wall.

Output: an .npz with
  obs    (N,19,8,8) float32   half-move observations (piece- and duck-phase)
  pi_idx (N,K)       int32     action indices with visit mass (-1 padding)
  pi_val (N,K)       float32   target probabilities (0 padding, rows sum to 1)
  z      (N,)        float32   outcome in [-1,1] from the position's side

Usage:
  # self-play (canonical ExIt)
  python -m DuckChess_Game.SBThree.gen_mcts_data --model models/duck_ppo/v2/v2_final.zip \
      --games 400 --sims 200 --workers 8 --out data/exit_iter1.npz
  # targeted games vs the depth-3 wall (our MCTS vs Peter d3)
  python -m DuckChess_Game.SBThree.gen_mcts_data --model <ckpt> --opponent peter \
      --peter-depths 3 --games 200 --sims 200 --workers 8 --out data/exit_d3.npz
  # fast smoke
  python -m DuckChess_Game.SBThree.gen_mcts_data --model <ckpt> --games 4 --sims 20 \
      --workers 2 --out data/exit_smoke.npz
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch

torch.distributions.Distribution.set_default_validate_args(False)

MOVE_CAP = 400          # half-move horizon (matches the 50-move-rule with margin)
DEFAULT_K = 16          # max visited actions stored per position (covers top-k + captures)


# ------------------------------------------------------------------ #
# Game loops (run inside each worker)                                  #
# ------------------------------------------------------------------ #

def _label(samples, winner):
    """Attach z to each (obs, idxs, pi, to_move) from its side's perspective."""
    out = []
    for obs, idxs, pi, to_move in samples:
        if winner in (None, "draw"):
            z = 0.0
        else:
            z = 1.0 if to_move == winner else -1.0
        out.append((obs, idxs, pi, np.float32(z)))
    return out


def _play_selfplay(mcts, rng, temp_moves, temperature, move_cap):
    """Both sides driven by the same MCTS; record targets for every turn."""
    from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine
    engine = _HeadlessEngine()
    engine.reset_game_state()
    samples, half, turns = [], 0, 0
    while not getattr(engine, "game_over", False) and half < move_cap:
        if engine.phase != "move_piece":
            break  # loop invariant: each iteration starts a full turn
        temp = temperature if turns < temp_moves else 0.0
        piece_a, duck_a, targets = mcts.choose_turn_with_targets(
            engine, temperature=temp, rng=rng)
        if piece_a is None:
            break
        samples.extend(targets)
        s, e = engine._decode_move(piece_a)
        engine.execute_move(s, e, animated=False)
        half += 1
        if not getattr(engine, "game_over", False) and engine.phase == "move_duck":
            if duck_a is None:
                valid = np.where(engine.action_masks())[0]
                if len(valid) == 0:
                    break
                duck_a = int(rng.choice(valid))
            _, de = engine._decode_move(duck_a)
            engine.place_duck(de, animated=False)
            half += 1
        turns += 1
    return _label(samples, getattr(engine, "winner", None)), getattr(engine, "winner", None)


def _play_vs_peter(mcts, opponent, learner_color, rng, temp_moves, temperature, move_cap):
    """Our MCTS vs the local Peter engine; record targets for OUR turns only.
    Every half-move (both sides) is mirrored to Peter's shadow engine."""
    from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine
    engine = _HeadlessEngine()
    engine.reset_game_state()
    opponent.reset()
    samples, half, turns = [], 0, 0
    while not getattr(engine, "game_over", False) and half < move_cap:
        masks = engine.action_masks()
        if not np.any(masks):
            break
        is_duck = engine.phase == "move_duck"
        if engine.turn == learner_color and engine.phase == "move_piece":
            temp = temperature if turns < temp_moves else 0.0
            piece_a, duck_a, targets = mcts.choose_turn_with_targets(
                engine, temperature=temp, rng=rng)
            if piece_a is None:
                break
            samples.extend(targets)
            s, e = engine._decode_move(piece_a)
            engine.execute_move(s, e, animated=False)
            opponent.mirror_action(piece_a, is_duck_phase=False)
            half += 1
            if not getattr(engine, "game_over", False) and engine.phase == "move_duck":
                if duck_a is None:
                    valid = np.where(engine.action_masks())[0]
                    if len(valid) == 0:
                        break
                    duck_a = int(rng.choice(valid))
                _, de = engine._decode_move(duck_a)
                engine.place_duck(de, animated=False)
                opponent.mirror_action(duck_a, is_duck_phase=True)
                half += 1
            turns += 1
        else:
            a = opponent.get_action(engine, masks)
            s, e = engine._decode_move(a)
            if engine.phase == "move_piece":
                engine.execute_move(s, e, animated=False)
            else:
                engine.place_duck(e, animated=False)
            opponent.mirror_action(a, is_duck_phase=is_duck)
            half += 1
    return _label(samples, getattr(engine, "winner", None)), getattr(engine, "winner", None)


def _stack(samples, K):
    """Pack variable-length (obs, idxs, pi, z) samples into padded arrays."""
    n = len(samples)
    obs = np.zeros((n, 19, 8, 8), np.float32)
    idx = np.full((n, K), -1, np.int32)
    val = np.zeros((n, K), np.float32)
    z = np.zeros((n,), np.float32)
    for i, (o, ids, pi, zz) in enumerate(samples):
        obs[i] = o
        ids = np.asarray(ids, np.int64)
        pi = np.asarray(pi, np.float64)
        if len(ids) > K:                       # keep the K highest-mass actions
            top = np.argsort(-pi)[:K]
            ids, pi = ids[top], pi[top]
            pi = pi / pi.sum() if pi.sum() > 0 else pi
        m = len(ids)
        idx[i, :m] = ids.astype(np.int32)
        val[i, :m] = pi.astype(np.float32)
        z[i] = zz
    return obs, idx, val, z


# ------------------------------------------------------------------ #
# Worker entry point (top-level for Windows 'spawn')                   #
# ------------------------------------------------------------------ #

def _worker(payload):
    (model_path, n_games, sims, c_puct, piece_topk, duck_topk, dirichlet,
     temp_moves, temperature, move_cap, opponent_kind, peter_depths, seed, K) = payload

    from sb3_contrib import MaskablePPO
    from DuckChess_Game.SBThree.mcts import DuckMCTS

    model = MaskablePPO.load(model_path, device="cpu")
    rng = np.random.default_rng(seed)
    all_samples, wld = [], {"win": 0, "loss": 0, "draw": 0}

    opps = None
    if opponent_kind == "peter":
        from DuckChess_Game.SBThree.peter_local import PeterLocalOpponent
        opps = {d: PeterLocalOpponent(depth=d, seed=seed + 1000 + d) for d in peter_depths}

    mcts = DuckMCTS(model, sims=sims, c_puct=c_puct,
                    piece_topk=piece_topk, duck_topk=duck_topk,
                    dirichlet=(dirichlet if opponent_kind == "self" else 0.0))

    for g in range(n_games):
        if opponent_kind == "self":
            recs, winner = _play_selfplay(mcts, rng, temp_moves, temperature, move_cap)
            # self-play has no fixed "learner"; tally from White's view for a sanity stat
            tag = "draw" if winner in (None, "draw") else ("win" if winner == "w" else "loss")
        else:
            depth = peter_depths[g % len(peter_depths)]
            learner = "w" if g % 2 == 0 else "b"
            recs, winner = _play_vs_peter(mcts, opps[depth], learner, rng,
                                          temp_moves, temperature, move_cap)
            tag = "draw" if winner in (None, "draw") else ("win" if winner == learner else "loss")
        wld[tag] += 1
        all_samples.extend(recs)

    return _stack(all_samples, K), wld


# ------------------------------------------------------------------ #
# Main                                                                #
# ------------------------------------------------------------------ #

def generate(model_path, games, sims, workers, out, *, opponent="self",
             peter_depths=(3,), c_puct=1.5, piece_topk=8, duck_topk=6,
             dirichlet=0.3, temp_moves=12, temperature=1.0, move_cap=MOVE_CAP,
             K=DEFAULT_K, seed=0, quiet=False):
    """Generate ExIt data; returns the output path. Importable by run_exit.py."""
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    workers = max(1, min(workers, games))
    per = [games // workers] * workers
    for i in range(games % workers):
        per[i] += 1

    payloads = [
        (model_path, per[w], sims, c_puct, piece_topk, duck_topk, dirichlet,
         temp_moves, temperature, move_cap, opponent, list(peter_depths),
         seed + 7919 * (w + 1), K)
        for w in range(workers) if per[w] > 0
    ]

    t0 = time.time()
    if not quiet:
        print(f"[gen_mcts] {games} games | sims={sims} | {len(payloads)} workers | "
              f"opp={opponent} | model={os.path.basename(model_path)}", flush=True)

    if len(payloads) == 1:
        results = [_worker(payloads[0])]
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(len(payloads)) as pool:
            results = pool.map(_worker, payloads)

    obs = np.concatenate([r[0][0] for r in results], axis=0)
    idx = np.concatenate([r[0][1] for r in results], axis=0)
    val = np.concatenate([r[0][2] for r in results], axis=0)
    z = np.concatenate([r[0][3] for r in results], axis=0)
    wld = {"win": 0, "loss": 0, "draw": 0}
    for _, w in results:
        for k in wld:
            wld[k] += w[k]

    np.savez_compressed(out, obs=obs, pi_idx=idx, pi_val=val, z=z)
    if not quiet:
        dt = time.time() - t0
        print(f"[gen_mcts] saved {len(z)} positions -> {out}  ({dt:.0f}s, "
              f"{games / max(1e-9, dt):.2f} games/s)", flush=True)
        print(f"[gen_mcts] game W/L/D (ref side) = "
              f"{wld['win']}/{wld['loss']}/{wld['draw']} | "
              f"z balance win={np.mean(z > 0):.1%} loss={np.mean(z < 0):.1%} "
              f"draw={np.mean(z == 0):.1%}", flush=True)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--games", type=int, default=400)
    p.add_argument("--sims", type=int, default=200)
    p.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    p.add_argument("--opponent", choices=("self", "peter"), default="self")
    p.add_argument("--peter-depths", type=int, nargs="+", default=[3])
    p.add_argument("--c-puct", type=float, default=1.5)
    p.add_argument("--piece-topk", type=int, default=8)
    p.add_argument("--duck-topk", type=int, default=6)
    p.add_argument("--dirichlet", type=float, default=0.3,
                   help="Root Dirichlet noise for self-play exploration (0=off)")
    p.add_argument("--temp-moves", type=int, default=12,
                   help="Sample from visit counts for the first N turns, then argmax")
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--move-cap", type=int, default=MOVE_CAP)
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    generate(args.model, args.games, args.sims, args.workers, args.out,
             opponent=args.opponent, peter_depths=tuple(args.peter_depths),
             c_puct=args.c_puct, piece_topk=args.piece_topk, duck_topk=args.duck_topk,
             dirichlet=args.dirichlet, temp_moves=args.temp_moves,
             temperature=args.temperature, move_cap=args.move_cap, K=args.k,
             seed=args.seed)


if __name__ == "__main__":
    main()
