# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Duck Chess is a Chess variant AI project — a fully playable Duck Chess game (chess with a "duck" piece that acts as a dynamic blocker) with a Pygame UI and a Reinforcement Learning agent trained via MaskablePPO (Stable Baselines3).

## Running the Code

### Game UI
```bash
python DuckChess_Game/UI/main.py
```

### RL Training

**Stage 11 (league-based):**
```bash
python DuckChess_Game/SBThree/train.py train
```

**Training against local Peter engine (with GUI, 4 envs):**
```bash
python DuckChess_Game/SBThree/train.py train-peter
```

**Headless Peter training (no GUI, background-safe, step-tracked):**
```bash
# Start fresh
python DuckChess_Game/SBThree/train_peter_headless.py --steps 10_000_000

# Resume from checkpoint
python DuckChess_Game/SBThree/train_peter_headless.py --checkpoint models/duck_ppo/peter_headless/peter_v5.zip

# Auto-resume from latest
python DuckChess_Game/SBThree/train_peter_headless.py --auto-resume

# View progress
python DuckChess_Game/SBThree/train_peter_headless.py --show-progress
```

**Run Stage 12 training:**
```bash
python DuckChess_Game/SBThree/train_stage12.py
```

### Testing
```bash
# Run all tests
pytest DuckChess_Game/Logic/test_logic.py -v

# Run specific test class
pytest DuckChess_Game/Logic/test_logic.py::TestGameInitialization -v

# Run with coverage
pytest DuckChess_Game/Logic/test_logic.py --cov=DuckChess_Game.Logic
```

### Monitoring Training

**TensorBoard:**
```bash
tensorboard --logdir tensorboard_logs/
```

**Headless training progress (real-time):**
```bash
tail -f logs/peter_training_progress.csv
```

## Architecture

The project is split into three modules under `DuckChess_Game/`:

### Logic (`DuckChess_Game/Logic/`)
Pure Python game engine. Uses a **Mixin composition pattern** — `logic.py` is the central hub inheriting from `MoveGenerationMixin`, `TurnManagerMixin`, `HistoryManagerMixin`, and `EndgameCheckerMixin`. Key abstractions:
- **Dual board representation**: Standard 2D array (`board_manager.py`) for UI/logic + 64-bit bitboards (`bitboard_manager.py`) for fast move generation.
- **RL interface**: `rl_mixin.py` exposes observation encoding and action masking to the training environment. Observations are a 19-channel tensor (12 piece planes + duck + en passant + castling + turn). Actions are a 4096-discrete space (64×64 board coordinates).
- `action_masker.py` enforces legal-move-only training — never allow the model to see invalid actions.

### UI (`DuckChess_Game/UI/`)
Pygame application. `main.py` is the entry point and uses the same **Mixin pattern**: `DuckChess` inherits `GameLogicMixin`, `RenderingMixin`, `InputHandlerMixin`, and `AssetManagerMixin`.
- `settings.py` — all visual constants (colors, fonts, layout, timing). Edit here for UI tweaks.
- Game states: `menu`, `rules`, `editor`, `game`. Input and rendering are split by state (e.g., `input_game.py` vs `input_menu.py`).
- The loaded RL model path is defined in `main.py` (currently `models/duck_ppo/stage10_league_v416.zip`).

### SBThree (`DuckChess_Game/SBThree/`)
RL training pipeline using **Stable Baselines3 + sb3-contrib MaskablePPO**.
- Custom Gymnasium environment in `duck_env_stage11_alpha.py` — wraps the Logic module.
- Training uses `SubprocVecEnv` with 8 parallel environments.
- **Curriculum design**: League-based opponents (30% alpha-beta AI from `ai.py`, 70% historical RL checkpoints). Sparse rewards (+1 win, -1 loss, 0 otherwise).
- Checkpoints are saved to `models/duck_ppo/`. TensorBoard logs go to `tensorboard_logs/`.

## Key Files

| File | Purpose |
|------|---------|
| `DuckChess_Game/Logic/logic.py` | Main game logic class — start here to understand game state |
| `DuckChess_Game/Logic/test_logic.py` | Unit tests for game logic (19 test classes) |
| `DuckChess_Game/Logic/rl_mixin.py` | Bridge between game engine and RL environments |
| `DuckChess_Game/Logic/observation_encoder.py` | Board → 19-channel tensor encoding |
| `DuckChess_Game/Logic/action_masker.py` | Legal move mask for 4096 action space |
| `DuckChess_Game/UI/main.py` | Game entry point, model loading, game loop |
| `DuckChess_Game/SBThree/train.py` | Multi-mode training script (stage 11, Peter, browser) |
| `DuckChess_Game/SBThree/train_peter_headless.py` | Headless Peter training with step tracking (background-safe) |
| `DuckChess_Game/SBThree/peter_local.py` | Local Peter engine opponent integration |
| `models/duck_ppo/` | Saved model checkpoints |
| `training_log.md` | Training history and stage-by-stage notes |
| `logs/` | Training logs, CSV progress tracking, TensorBoard events |

## Duck Chess Rules

In Duck Chess, after every normal move a player must also move the "duck" — a neutral piece that cannot be captured and blocks any square it occupies. The duck cannot start on the square it currently occupies. This is enforced in `rules_checker.py` and reflected in the two-phase action structure of the RL environment.
