# Duck Chess AI 🦆

A complete **Duck Chess** engine, a polished Pygame interface, and a reinforcement-learning
agent trained with MaskablePPO — built as a Computer Science final project.

> **Duck Chess** is a chess variant with one extra twist: after *every* move, the player must
> also move a neutral **duck**. The duck can't be captured, blocks whatever square it stands on,
> and never leaves the board. It turns a deterministic game into a constant tactical puzzle.

![Main menu](menu.png)
![In-game](game_play.png)

---

## Table of Contents

- [What makes Duck Chess different](#what-makes-duck-chess-different)
- [Features](#features)
- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Architecture](#architecture)
- [The reinforcement-learning pipeline](#the-reinforcement-learning-pipeline)
- [Testing](#testing)
- [Tech stack](#tech-stack)
- [Documentation map](#documentation-map)

---

## What makes Duck Chess different

Three rules separate Duck Chess from standard chess. All three are enforced by the engine
in [`DuckChess_Game/Logic/`](DuckChess_Game/Logic):

| Rule | What it means | Where it lives |
|------|---------------|----------------|
| **The duck** | A neutral blocker is moved after every normal move. It can't be captured, it blocks any square it sits on, and it may not stay on its current square. | [`rules_checker.py`](DuckChess_Game/Logic/rules_checker.py), two-phase turn pipeline |
| **Win by king capture** | There is **no check or checkmate**. You win the instant you *capture* the enemy king. | [`turn_manager.py`](DuckChess_Game/Logic/turn_manager.py) |
| **Fowling** | A player with **no legal moves *wins*** (the opposite of stalemate in standard chess). | [`endgame_checker.py`](DuckChess_Game/Logic/endgame_checker.py) |

Draws happen only by the **50-move rule** (100 half-moves with no progress).

Each turn is therefore **two phases**: *move a piece*, then *move the duck*. That structure shows
up everywhere — in the UI input handling, and as the two-stage action space the RL agent learns.

---

## Features

- **Pure-Python engine** — legal move generation, castling, en passant, promotion, and duck
  blocking, with a dual board representation (a readable 2D array *and* 64-bit bitboards for speed).
- **Full Pygame UI** — menu, interactive rules screen, a position editor, and live play with
  move highlighting, animations, sound, and a game-over screen.
- **Reinforcement-learning pipeline** — a custom Gymnasium environment, strict legal-action
  masking, and a 13-stage curriculum trained with `sb3-contrib`'s MaskablePPO.
- **A real engine opponent ("Peter")** — training and evaluation against a local alpha-beta
  chess engine, so model strength is measured against ground truth, not just self-play.
- **277-test suite** — fast, headless `pytest` coverage of the engine, the RL interface, and
  the opponents (see [TESTING.md](TESTING.md)).
- **Formal test docs** — a Software Test Plan and Software Test Design under [`docs/`](docs).

---

## Quick start

### 1. Prerequisites

- **Python 3.12**
- A virtual environment (the repo expects a local `.venv/`)

### 2. Install dependencies

There is no `requirements.txt`; install the runtime dependencies directly:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install pygame numpy torch stable-baselines3 sb3-contrib gymnasium pytest pytest-cov
```

> Versions this project is developed against: `stable-baselines3` 2.8, `sb3-contrib` 2.8,
> `gymnasium` 1.2, `numpy` 2.4, `pygame` 2.6, `torch` 2.11 (CPU). A GPU is **not** required.

### 3. Play the game

```bash
python DuckChess_Game/UI/main.py
```

> **Note on the AI opponent:** the UI currently loads **no** RL model
> (`model_path = None` in [`main.py`](DuckChess_Game/UI/main.py)). This is deliberate — every
> trained checkpoint so far either loses to the real Peter engine or only wins via a narrow
> "king-rush" exploit that a thinking human can refute. The game is fully playable
> human-vs-human; wiring in a model is a one-line change once a checkpoint clears that bar.

### 4. Run the tests

```bash
pytest
```

That runs the canonical 277-test suite in [`tests/`](tests) (configured via `pytest.ini`).

---

## Repository layout

```
duck_chess/
├── DuckChess_Game/
│   ├── Logic/        Pure-Python game engine (rules, bitboards, RL bridge)
│   ├── UI/           Pygame application (menu, editor, play, rendering)
│   └── SBThree/      RL training & evaluation pipeline (MaskablePPO)
├── tests/            Canonical pytest suite (277 tests)
├── docs/             Formal Software Test Plan (STP) & Test Design (STD)
├── models/duck_ppo/  Saved model checkpoints, organized by stage
├── logs/             Training logs, CSV progress, TensorBoard events
├── assets/           Piece sprites, sounds, rules text
├── web_ui/           Standalone browser build of the board (experimental)
├── README.md         You are here
├── CLAUDE.md         Guidance for AI coding assistants
├── TESTING.md        How to run and extend the test suite
├── HEADLESS_TRAINING.md  Running long training jobs in the background
└── training_log.md   Stage-by-stage training history and results
```

---

## Architecture

The codebase is three modules under `DuckChess_Game/`, each built with a **mixin composition
pattern** — a central class inherits focused behaviour from several mixins.

### Logic — the engine
`logic.py` is the hub, composing `MoveGenerationMixin`, `TurnManagerMixin`,
`HistoryManagerMixin`, and `EndgameCheckerMixin`.

- **Dual board representation:** a 2D array ([`board_manager.py`](DuckChess_Game/Logic/board_manager.py))
  for clarity, plus 64-bit bitboards ([`bitboard_manager.py`](DuckChess_Game/Logic/bitboard_manager.py))
  for fast move generation. A validator keeps the two in sync.
- **RL bridge:** [`rl_mixin.py`](DuckChess_Game/Logic/rl_mixin.py) exposes observation encoding
  and action masking to the training environment.

### UI — the Pygame app
`main.py` composes `GameLogicMixin`, `RenderingMixin`, `InputHandlerMixin`, and
`AssetManagerMixin`. Game states are `menu`, `rules`, `editor`, and `game`; input and rendering
are split per state. All visual constants live in
[`settings.py`](DuckChess_Game/UI/settings.py).

### SBThree — the RL pipeline
A Gymnasium environment wraps the engine; training uses `SubprocVecEnv` with 8 parallel
environments and MaskablePPO. League-based and engine-based opponents drive a curriculum.
See [the next section](#the-reinforcement-learning-pipeline).

---

## The reinforcement-learning pipeline

The agent learns the game's quirks — especially **defensive duck placement** and the two-phase
turn — through a staged curriculum. Full results are in [training_log.md](training_log.md);
the short version:

| Concept | How it's modeled |
|---------|------------------|
| **Observation** | A `19 × 8 × 8` tensor: 12 piece planes + duck + en passant + castling + turn. |
| **Action space** | `4096` discrete actions (`64 × 64` from/to squares), with the duck phase using the same space. |
| **Action masking** | [`action_masker.py`](DuckChess_Game/Logic/action_masker.py) makes illegal actions unselectable — the policy never sees an invalid move. |
| **Curriculum** | Stage 1 (random) → greedy → dense-reward mechanics → self-play → league play → alpha-beta punisher → engine grounding vs **Peter**. |
| **Reward** | Sparse terminal (+1 win / −1 loss / +0.1 draw) for league stages; dense shaping for corrective runs that need a per-move gradient. |
| **Ground truth** | [`eval_vs_peter.py`](DuckChess_Game/SBThree/eval_vs_peter.py) reports real W/L/D against the Peter engine — the metric that revealed self-play models were weaker than they looked. |

**Run training:**

```bash
# Stage 11 league self-play
python DuckChess_Game/SBThree/train.py train

# Against the local Peter engine, with GUI (4 envs)
python DuckChess_Game/SBThree/train.py train-peter

# Headless / background-safe, with step tracking and resume
python DuckChess_Game/SBThree/train_peter_headless.py --steps 10_000_000
```

See [HEADLESS_TRAINING.md](HEADLESS_TRAINING.md) for long, unattended runs (nohup, `pythonw`,
PowerShell jobs, `screen`), resuming from checkpoints, and TensorBoard monitoring.

---

## Testing

The canonical suite lives in [`tests/`](tests) — **277 tests** across 14 files covering the
bitboard manager, rules checker, move generation, action masker, observation encoder, move
pipeline, game-state validator, the RL environment, and the Peter opponents.

```bash
pytest                              # full suite (testpaths=tests via pytest.ini)
pytest tests/test_rules_checker.py  # one module
pytest --cov=DuckChess_Game.Logic   # with coverage
```

A separate, smaller smoke test lives at
[`DuckChess_Game/Logic/test_logic.py`](DuckChess_Game/Logic/test_logic.py) (26 tests). Full
details, the headless test setup, and troubleshooting are in [TESTING.md](TESTING.md).

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12 |
| Game UI | Pygame |
| RL framework | Stable-Baselines3 + sb3-contrib (MaskablePPO) |
| RL environment | Gymnasium |
| Numerics / tensors | NumPy, PyTorch (CPU) |
| Testing | pytest, pytest-cov |
| Monitoring | TensorBoard |

---

## Documentation map

| Document | What it covers |
|----------|----------------|
| [README.md](README.md) | Project overview and quick start (this file) |
| [CLAUDE.md](CLAUDE.md) | Architecture and commands for AI coding assistants |
| [TESTING.md](TESTING.md) | Running, reading, and extending the test suite |
| [HEADLESS_TRAINING.md](HEADLESS_TRAINING.md) | Long, unattended training runs |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Current build status at a glance |
| [training_log.md](training_log.md) | Stage-by-stage training history and results |
| [docs/STP-DUCK-001.md](docs/STP-DUCK-001.md) | Formal Software Test Plan |
| [docs/STD-DUCK-001.md](docs/STD-DUCK-001.md) | Formal Software Test Design |
