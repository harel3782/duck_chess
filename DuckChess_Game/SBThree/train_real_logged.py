#!/usr/bin/env python
"""
train_real_logged.py — 1-hour training continuation with replay saving.

Loads the final model from the 14-hour run and trains for 1 hour,
capturing all games to disk.

Usage:
  cd DuckChess_Game/SBThree && python train_real_logged.py
  OR from project root:
  python DuckChess_Game/SBThree/train_real_logged.py
"""
import os
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import SubprocVecEnv

from DuckChess_Game.SBThree.peter_local import PeterLocalEnv, make_peter_config
from DuckChess_Game.SBThree.base.reward_calculator import ShapedReward

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
MODEL_PATH = "models/duck_ppo/real/real_final.zip"
OUTPUT_DIR = "models/duck_ppo/real_replays"
TOTAL_TIMESTEPS = 3_600_000  # ~1 hour @ ~1000 fps (but slower due to Peter)
CHECKPOINT_INTERVAL = 50_000
NUM_ENVS = 8
DEPTH = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)

log.info("="*70)
log.info("TRAINING WITH REPLAY SAVING — 1 hour continuation")
log.info("="*70)
log.info(f"Model:     {MODEL_PATH}")
log.info(f"Duration:  ~1 hour (~{TOTAL_TIMESTEPS:,} timesteps)")
log.info(f"Depth:     Peter d{DEPTH}")
log.info(f"Replays:   saved_replays/real_replays_d3/")
log.info(f"Output:    {OUTPUT_DIR}")
log.info("="*70 + "\n")

# Create environment factory with replay saving ENABLED
def make_env(rank):
    config = make_peter_config(
        depth=DEPTH,
        stage_name="real_replays_d3",
        randomize_color=True,
        replay_every=1,  # ← SAVE EVERY GAME
    )
    config.reward = ShapedReward(
        material_weight=0.05,
        loss_multiplier=1.3,
        development_bonus=0.08,
        castling_bonus=0.20,
        defense_weight=0.05,
        mobility_scale=0.004,
        blocking_scale=0.015,
        step_penalty=0.0,
        king_push_bonus=0.0,
        draw=0.1,
    )
    return PeterLocalEnv(config, env_index=rank)

# Load existing model
log.info(f"Loading model: {MODEL_PATH}")
model = MaskablePPO.load(MODEL_PATH, device="cpu")

# Create vectorized environment
log.info(f"Creating {NUM_ENVS} parallel environments...")
env = SubprocVecEnv([lambda r=i: make_env(r) for i in range(NUM_ENVS)])
model.set_env(env)

# Train
log.info(f"Starting training loop...\n")
t_start = datetime.now()

try:
    model.learn(
        total_timesteps=TOTAL_TIMESTEPS,
        callback=None,
    )
except KeyboardInterrupt:
    log.info("Training interrupted by user")

t_end = datetime.now()
elapsed = (t_end - t_start).total_seconds()
log.info(f"\n{'='*70}")
log.info(f"Training completed in {elapsed/3600:.2f} hours")
log.info(f"{'='*70}")

# Save final checkpoint
final_path = os.path.join(OUTPUT_DIR, "final_with_replays.zip")
model.save(final_path)
log.info(f"✓ Saved: {final_path}")

log.info(f"\n📁 Replays saved to:")
log.info(f"   saved_replays/real_replays_d3/")
log.info(f"\nView the replay files with a replay viewer to see how the model plays.")
