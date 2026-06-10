#!/usr/bin/env python
"""
play_games.py — Play games with a trained model and save replays.

Usage from project root:
  python DuckChess_Game/SBThree/play_games.py --model models/duck_ppo/real/real_final.zip --games 10 --depth 3
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../..")

import argparse
import numpy as np
from sb3_contrib import MaskablePPO
from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config

def play_games(model_path, games=10, depth=3):
    """Play games and save replays."""
    print(f"\n{'='*70}")
    print(f"Playing {games} games with {os.path.basename(model_path)}")
    print(f"Opponent: Peter depth-{depth}")
    print(f"Replays saved to: saved_replays/game_replays_d{depth}/")
    print(f"{'='*70}\n")

    model = MaskablePPO.load(model_path, device="cpu")

    # Config with replay saving enabled
    config = make_peter_config(
        depth=depth,
        stage_name=f"game_replays_d{depth}",
        replay_every=1,  # Save EVERY game
    )
    env = PeterLocalEnv(config, env_index=1)

    wins = losses = draws = 0

    for g in range(games):
        obs, _ = env.reset()
        terminated = truncated = False
        steps = 0

        while not (terminated or truncated):
            masks = env.action_masks()
            if not np.any(masks):
                break
            action, _ = model.predict(obs, action_masks=masks, deterministic=False)
            obs, reward, terminated, truncated, _ = env.step(int(action))
            steps += 1

        winner = getattr(env.engine, "winner", None)
        lc = env.learning_color

        if winner == "draw" or winner is None:
            draws += 1
            result = "DRAW"
        elif winner == lc:
            wins += 1
            result = "WIN "
        else:
            losses += 1
            result = "LOSS"

        print(f"  Game {g+1:>2}/{games}  agent={lc}  {steps:>3} halfmoves  →  {result}")

    print(f"\n{'='*70}")
    print(f"Results: W/L/D = {wins}/{losses}/{draws}")
    print(f"Win rate: {wins/games*100:.0f}%")
    print(f"{'='*70}\n")
    print(f"✓ Replays saved to: saved_replays/game_replays_d{depth}/")
    print(f"  Total files: {wins + losses + draws}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="models/duck_ppo/real/real_final.zip")
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--depth", type=int, default=3)
    args = p.parse_args()

    play_games(args.model, games=args.games, depth=args.depth)
