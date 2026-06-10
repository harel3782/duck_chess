#!/usr/bin/env python
"""
train_peter_headless.py — Headless (no GUI) Peter training with step logging.

Designed to:
  • Run without pygame or X11 (runs on remote servers, screen-off, etc.)
  • Track training progress to a CSV file with step counts
  • Support resuming from checkpoints
  • Provide detailed epoch/step statistics

Usage:
  # Start fresh training
  python train_peter_headless.py --depths 1 2 3 3 --steps 10_000_000

  # Resume from checkpoint
  python train_peter_headless.py --checkpoint models/duck_ppo/peter_headless/peter_v5.zip

  # Check progress
  tail -f logs/peter_training_progress.csv

  # Run in background (Linux/Mac)
  nohup python train_peter_headless.py --steps 10_000_000 > logs/peter_train.log 2>&1 &

  # Run in background (Windows)
  pythonw train_peter_headless.py --depths 1 2 3 3 --steps 10_000_000
"""

import os
import sys
import csv
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

torch.distributions.Distribution.set_default_validate_args(False)

from DuckChess_Game.SBThree.peter_local import make_peter_mixed_env_factories


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(log_dir="logs"):
    """Configure logging to both file and stdout."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    log_file = os.path.join(log_dir, f"peter_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ]
    )
    return logging.getLogger(__name__)


# ============================================================================
# Progress Tracking Callback
# ============================================================================

class HeadlessProgressCallback(BaseCallback):
    """Track and log training progress to CSV."""

    def __init__(self, csv_path, checkpoint_dir, checkpoint_every=200_000):
        super().__init__()
        self.csv_path = csv_path
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_every = checkpoint_every
        self.last_checkpoint_step = 0
        self.start_time = time.time()
        self.last_log_step = 0
        self.log_frequency = 10_000  # Log every N steps

        # Initialize CSV with headers
        Path(self.csv_path).parent.mkdir(parents=True, exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'total_steps',
                    'elapsed_seconds',
                    'steps_per_second',
                    'mean_reward',
                    'mean_length',
                    'checkpoint_saved',
                ])

    def _on_step(self) -> bool:
        steps = self.num_timesteps

        # Log periodically
        if steps - self.last_log_step >= self.log_frequency or steps == self.checkpoint_every:
            elapsed = time.time() - self.start_time
            sps = steps / elapsed if elapsed > 0 else 0

            # Get some training stats if available
            mean_reward = getattr(self.model, 'mean_reward', None)
            mean_length = getattr(self.model, 'mean_episode_length', None)

            checkpoint_saved = False

            # Checkpoint every N steps
            if steps - self.last_checkpoint_step >= self.checkpoint_every:
                os.makedirs(self.checkpoint_dir, exist_ok=True)
                checkpoint_path = os.path.join(
                    self.checkpoint_dir,
                    f"peter_headless_v{steps // self.checkpoint_every}.zip"
                )
                self.model.save(checkpoint_path)
                checkpoint_saved = True
                self.last_checkpoint_step = steps
                print(f"\n[CHECKPOINT] Saved to {os.path.basename(checkpoint_path)}")

            # Write to CSV
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    steps,
                    int(elapsed),
                    f"{sps:.2f}",
                    f"{mean_reward:.4f}" if mean_reward else "N/A",
                    f"{mean_length:.1f}" if mean_length else "N/A",
                    "YES" if checkpoint_saved else "NO",
                ])

            # Print to console
            print(
                f"[{steps:,} steps | {elapsed:,}s | {sps:.1f} steps/s] "
                f"Checkpoint: {'✓' if checkpoint_saved else '·'}"
            )

            self.last_log_step = steps

        return True


# ============================================================================
# Training Functions
# ============================================================================

def train_peter_headless(
    base_model_path=None,
    depths=(1, 2, 3, 3),
    total_timesteps=10_000_000,
    checkpoint_every=200_000,
    n_envs=4,
    log_dir="logs",
    model_dir="models/duck_ppo/peter_headless",
):
    """
    Train MaskablePPO against local Peter engine without GUI.

    Parameters
    ----------
    base_model_path : str | None
        Path to a .zip checkpoint to warm-start from.
    depths : tuple[int, ...]
        Search depth per parallel environment.
    total_timesteps : int
        Total environment steps to train for.
    checkpoint_every : int
        Save a checkpoint every this many timesteps.
    n_envs : int
        Number of parallel environments.
    log_dir : str
        Directory for logs and progress tracking.
    model_dir : str
        Directory where to save checkpoints.
    """
    logger = setup_logging(log_dir)
    logger.info("=" * 80)
    logger.info("Peter Headless Training Started")
    logger.info("=" * 80)
    logger.info(f"Config: depths={depths}, total_steps={total_timesteps:,}, "
                f"checkpoint_every={checkpoint_every:,}, n_envs={n_envs}")

    # Create progress CSV
    csv_path = os.path.join(log_dir, "peter_training_progress.csv")

    # Create environment
    logger.info(f"Creating {n_envs} parallel environments...")
    vec_env = SubprocVecEnv(make_peter_mixed_env_factories(list(depths)))
    logger.info("Environments created.")

    # Custom objects for model
    custom_objects = {
        "learning_rate": 3e-4,
        "ent_coef": 0.01,
        "target_kl": 0.05,
    }

    # Load or create model
    tb_log_dir = os.path.join(log_dir, "tensorboard_logs")
    if base_model_path and os.path.exists(base_model_path):
        logger.info(f"Loading checkpoint: {base_model_path}")
        model = MaskablePPO.load(
            base_model_path,
            env=vec_env,
            tensorboard_log=tb_log_dir,
            custom_objects=custom_objects,
        )
        logger.info("Model loaded successfully.")
    else:
        if base_model_path:
            logger.warning(f"Base model not found: {base_model_path}. Starting fresh.")
        logger.info("Creating fresh MaskablePPO model...")
        model = MaskablePPO(
            "MlpPolicy",
            vec_env,
            learning_rate=3e-4,
            ent_coef=0.01,
            target_kl=0.05,
            n_steps=512,
            batch_size=256,
            verbose=1,
            tensorboard_log=tb_log_dir,
            device="auto",
        )
        logger.info("Model created.")

    # Create callback
    callback = HeadlessProgressCallback(
        csv_path=csv_path,
        checkpoint_dir=model_dir,
        checkpoint_every=checkpoint_every,
    )

    # Train
    logger.info(f"Starting training for {total_timesteps:,} timesteps...")
    logger.info(f"Progress tracked in: {csv_path}")
    logger.info(f"TensorBoard logs in: {tb_log_dir}")
    start_time = time.time()

    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=callback,
            tb_log_name="peter_headless",
        )
    except KeyboardInterrupt:
        logger.info("Training interrupted by user.")
    except Exception as e:
        logger.error(f"Training failed with error: {e}", exc_info=True)
        raise
    finally:
        elapsed = time.time() - start_time
        logger.info(f"Training completed in {elapsed/3600:.1f} hours.")

        # Save final model
        final_path = os.path.join(model_dir, "peter_headless_final.zip")
        os.makedirs(model_dir, exist_ok=True)
        model.save(final_path)
        logger.info(f"Final model saved: {final_path}")
        logger.info("=" * 80)


# ============================================================================
# Resume / Status Functions
# ============================================================================

def show_progress(log_dir="logs"):
    """Display recent training progress from CSV."""
    csv_path = os.path.join(log_dir, "peter_training_progress.csv")
    if not os.path.exists(csv_path):
        print(f"No progress file found: {csv_path}")
        return

    with open(csv_path, 'r') as f:
        lines = f.readlines()
        if len(lines) > 1:
            print("\n" + "=" * 80)
            print("Recent Training Progress (last 10 entries):")
            print("=" * 80)
            # Print header
            print(lines[0].strip())
            # Print last 10 lines
            for line in lines[-10:]:
                print(line.strip())
            print("=" * 80 + "\n")


def find_latest_checkpoint(model_dir="models/duck_ppo/peter_headless"):
    """Find the most recent checkpoint in the model directory."""
    if not os.path.exists(model_dir):
        return None

    checkpoints = sorted(
        [f for f in os.listdir(model_dir) if f.endswith('.zip')],
        key=lambda x: os.path.getctime(os.path.join(model_dir, x)),
        reverse=True
    )

    if checkpoints:
        return os.path.join(model_dir, checkpoints[0])
    return None


# ============================================================================
# Main / CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Headless Peter training with step tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start fresh training (4 envs, depths 1,2,3,3)
  python train_peter_headless.py --steps 10000000

  # Resume from specific checkpoint
  python train_peter_headless.py --checkpoint models/duck_ppo/peter_headless/peter_v5.zip

  # Auto-resume from latest checkpoint
  python train_peter_headless.py --auto-resume

  # Show progress from existing run
  python train_peter_headless.py --show-progress
        """
    )

    parser.add_argument(
        "--depths",
        nargs="+",
        type=int,
        default=[1, 2, 3, 3],
        help="Search depth per environment (default: 1 2 3 3)"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=10_000_000,
        help="Total training timesteps (default: 10,000,000)"
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=200_000,
        help="Save checkpoint every N steps (default: 200,000)"
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path to checkpoint to resume from"
    )
    parser.add_argument(
        "--auto-resume",
        action="store_true",
        help="Automatically resume from latest checkpoint if found"
    )
    parser.add_argument(
        "--show-progress",
        action="store_true",
        help="Show recent training progress and exit"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs",
        help="Directory for logs (default: logs)"
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="models/duck_ppo/peter_headless",
        help="Directory for model checkpoints (default: models/duck_ppo/peter_headless)"
    )

    args = parser.parse_args()

    if args.show_progress:
        show_progress(args.log_dir)
        return

    # Determine checkpoint to load
    checkpoint_path = args.checkpoint
    if args.auto_resume and not checkpoint_path:
        checkpoint_path = find_latest_checkpoint(args.model_dir)
        if checkpoint_path:
            print(f"[AUTO-RESUME] Found checkpoint: {checkpoint_path}")

    # Train
    train_peter_headless(
        base_model_path=checkpoint_path,
        depths=tuple(args.depths),
        total_timesteps=args.steps,
        checkpoint_every=args.checkpoint_every,
        n_envs=len(args.depths),
        log_dir=args.log_dir,
        model_dir=args.model_dir,
    )


if __name__ == "__main__":
    main()
