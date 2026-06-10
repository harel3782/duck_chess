#!/usr/bin/env python
"""Quick test to verify replay saving works."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from sb3_contrib import MaskablePPO
from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config

print("Loading model...")
model = MaskablePPO.load("models/duck_ppo/real/real_final.zip", device="cpu")

print("Creating environment with replay saving...")
config = make_peter_config(depth=3, stage_name="test_replay", replay_every=1, replay_chief_only=False)
env = PeterLocalEnv(config, env_index=0)

print(f"Config replay_dir: {config.replay_dir}")
print(f"Config stage_name: {config.stage_name}")
print(f"Config replay_every: {config.replay_every}")
print(f"Config replay_chief_only: {config.replay_chief_only}")

print("\nPlaying 3 test games...")
for game_num in range(1, 4):
    print(f"\nGame {game_num}:")
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
    print(f"  Result: {winner}, Steps: {steps}")

print("\n✓ Testing complete. Check saved_replays/test_replay/ for files.")
