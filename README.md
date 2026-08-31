---
title: Duck Chess AI
emoji: 🦆
colorFrom: yellow
colorTo: green
sdk: gradio
app_port: 7860
pinned: false
---

# Duck Chess AI 🦆

A complete **Duck Chess** engine, a FastAPI web front-end, and a reinforcement-learning agent
trained with MaskablePPO and played with AlphaZero-style MCTS — built as a Computer Science final
project.

> **Duck Chess** is a chess variant with one extra twist: after *every* move, the player must also
> move a neutral **duck**. The duck can't be captured, blocks whatever square it stands on, and
> never leaves the board. It turns a deterministic game into a constant tactical puzzle.

---

## Table of Contents

- [What makes Duck Chess different](#what-makes-duck-chess-different)
- [Key results & lessons learned](#key-results--lessons-learned)
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

Three rules separate Duck Chess from standard chess. All three are enforced by the engine in
[`DuckChess_Game/Logic/`](DuckChess_Game/Logic):

| Rule | What it means | Where it lives |
|------|---------------|----------------|
| **The duck** | A neutral blocker is moved after every normal move. It can't be captured, it blocks any square it sits on, and it may not stay on its current square. | [`rules_checker.py`](DuckChess_Game/Logic/rules_checker.py) + the two-phase turn pipeline |
| **Win by king capture** | There is **no check or checkmate**. You win the instant you *capture* the enemy king. | [`turn_manager.py`](DuckChess_Game/Logic/turn_manager.py) |
| **Fowling** | A player with **no legal moves *wins*** (the opposite of stalemate). | [`endgame_checker.py`](DuckChess_Game/Logic/endgame_checker.py) |

Draws happen only by the **50-move rule** (100 half-moves with no progress).

Each turn is therefore **two phases**: *move a piece*, then *move the duck*. That structure shows up
everywhere — in the UI input handling, and as the two-stage action space the RL agent learns.

---

## Key results & lessons learned

The short version of the project's actual findings — full detail in
[docs/training_log.md](docs/training_log.md) and [PLAN_V2.md](PLAN_V2.md).

| Finding | What happened |
|---|---|
| **Self-play strength ≠ real strength** | The Stage 10/12 self-play league dominated internally but lost **0/20** to the Peter engine at depth-2. This is why every later stage is measured against an independent engine, not self-play — see [Peter](#peter-the-ground-truth-opponent) below. |
| **The king-rush exploit** | Models converged on a cheap ~4-move king-rush that beat shallow opponents but lost to Peter depth-3 and to a human. Caused by three things acting together: a **fixed opponent**, a **fixed starting position**, and **dense shaped reward**. |
| **v2 — fixing the root cause, not the symptom** | Removing all three causes at once (an opponent pool, random starting positions, sparse terminal reward) produced the first non-exploiting model: **95% (19/1) vs Peter depth-2**, trained from scratch. |
| **"A value head evaluates; the policy chooses"** | Using the value head to directly pick moves (alpha-beta with value-argmax) collapsed performance from 95% to **0%**. AlphaZero-style MCTS — policy guides *where* to search, value only *scores* what's found — restored it to **100% (12/0)**. |
| **Open problem: the depth-3 wall** | No model has beaten Peter depth-3 yet, with or without search (0% even at 1,200 MCTS simulations). Expert Iteration (MCTS self-play → retrain on it → repeat) is the current attempt to crack it. |

---

## Features

- **Pure-Python engine** — legal move generation, castling, en passant, promotion, and duck
  blocking, with a dual board representation (a readable 2D array *and* 64-bit bitboards for speed).
- **Browser web UI** — a FastAPI + JS app (`web_ui/`) to play any trained checkpoint or a
  local 2-player game, with a model browser, save / load / replay (duck included), per-player
  timers, and board flip. See [Quick start](#3-play-in-the-browser-web-ui).
- **Reinforcement-learning pipeline** — a custom Gymnasium environment, strict legal-action masking,
  a staged curriculum trained with `sb3-contrib`'s MaskablePPO, and an **AlphaZero-style PUCT MCTS**
  (`mcts.py`) for inference-time search.
- **A real engine opponent ("Peter")** — training and evaluation against Peter, so model strength is
  measured against ground truth, not just self-play. See below.
- **A headless test suite** — fast, no-display `pytest` coverage of the engine, the RL interface, and
  the opponents (see [TESTING.md](docs/TESTING.md)).
- **Formal test docs** — a Software Test Plan (STP) and Software Test Design (STD) under
  [`docs/`](docs).

### Peter — the ground-truth opponent

**Peter** is an existing Duck Chess engine found online and integrated into this project (via
[`peter_local.py`](DuckChess_Game/SBThree/peter_local.py)) — it is **not** built in-house. It's kept
separate from the project's own in-house alpha-beta opponent,
[`AlphaBetaOpponent`](DuckChess_Game/SBThree/base/opponent_strategy.py), which is used only as one of
several league opponents during training. (`DuckChess_Game/Logic/ai.py` is a different, simpler
random-move fallback used only by the desktop UI when no model is loaded — it does not run search.)

Peter matters because it's *independent*: self-play results repeatedly looked strong while the
underlying model was actually weak (see [Key results](#key-results--lessons-learned) above), so every
serious strength claim in this project is measured against Peter — not against the model's own
history — via [`eval_vs_peter.py`](DuckChess_Game/SBThree/eval_vs_peter.py).

---

## Quick start

### 1. Prerequisites

- **Python 3.12**
- A virtual environment (the repo expects a local `.venv/`)

### 2. Install dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

> Developed against **Python 3.12** with `stable-baselines3` 2.8, `sb3-contrib` 2.8,
> `gymnasium` 1.2, `numpy` 2.4, `torch` 2.11 (CPU), `fastapi` 0.136,
> `uvicorn` 0.49. A GPU is **not** required. Exact pins live in
> [`requirements.txt`](requirements.txt).

### 3. Play in the browser (web UI)

A FastAPI + vanilla-JS web app under [`web_ui/`](web_ui) plays Duck Chess in the browser
against any trained checkpoint, or in local 2-player mode. Run it from the **project root**:

```bash
python -m uvicorn web_ui.server:app --port 7890
# or simply:
python web_ui/server.py
```

Then open **http://127.0.0.1:7890** in a real browser (Chrome / Edge / Firefox). It is a
**local development server** — login is open (any name), game state is kept in memory plus
optional JSON saves; don't expose it to a network.

**What the web UI does (all implemented in `web_ui/server.py` + `index.html`):**

- **Model browser** — the opponent dropdown is auto-populated by scanning
  `models/duck_ppo/` for every `*.zip` checkpoint (grouped by folder, `final`/`latest`
  first). Models load lazily on first use, on CPU.
- **Play vs a model** as White or Black (the board auto-flips when you play Black, and the
  model moves first), or **2-player local** (human vs human, no model).
- **Two-phase turns** — move a piece (legal moves and captures are highlighted), then place
  the duck on a highlighted square; the model then plays its full turn.
- **Move history, captured pieces, a material evaluation bar,** and **per-player timers.**
- **Board flip, resign,** and **undo** (one half-turn in 2-player; a full human+model round
  vs a model).
- **Game-over screen** that names the reason: king capture, fowling, resignation, or the
  50-move draw.
- **Save / load / review** — save a finished game to `saved_replays/web/`, then **Load &
  Review** it from the menu: step Prev / Next / Play through the game with the **duck moving
  per step** and the current move highlighted. Saved games can be **deleted** from the list
  (inline two-step confirm).
- **Keyboard shortcuts:** `F` flip, `R` resign, `←/→` step through past positions, `Esc`
  close a modal / leave history view.

> Model *strength* is measured against the Peter engine, not self-play — the web UI simply lets
> you load and play any checkpoint.

### 4. Run the tests

```bash
pytest
```

This runs the canonical suite in [`tests/`](tests) (configured via `pytest.ini`). See
[Testing](#testing) for the real pass/fail picture and the optional web/e2e layers.

---

## Repository layout

```
duck_chess/
├── DuckChess_Game/
│   ├── Logic/        Pure-Python game engine (rules, bitboards, RL bridge)
│   └── SBThree/      RL training, search (MCTS), and evaluation pipeline
├── web_ui/           FastAPI + JS web app (server.py, index.html): play vs a model or 2-player, save/replay
├── tests/            Canonical pytest suite (engine + RL + web/e2e layers)
├── models/duck_ppo/  Saved model checkpoints, organized by stage/run
├── logs/             Training logs, CSV progress
├── tensorboard_logs/ TensorBoard event files (git-ignored)
├── saved_replays/    Training replays; web game saves under saved_replays/web/
├── scripts/          Utility scripts (build launcher, replay viewers, debug)
├── assets/           Duck sprite/favicon served by the web UI at /assets (plus legacy sprites/sounds)
├── requirements.txt  Pinned Python dependencies
├── README.md         You are here
├── CLAUDE.md         Guidance for AI coding assistants
├── PLAN_V2.md        The v2 + search + Expert-Iteration plan and its results
└── docs/             Test plan/design (STP/STD), training log, testing & web-UI notes
```

---

## Architecture

The codebase is two Python modules under `DuckChess_Game/` plus the `web_ui/` package. Each Python
module is built with a **mixin composition pattern** — a central class inherits focused behaviour
from several mixins.

### Logic — the engine
`logic.py` defines the hub class `GameLogicMixin`, composing `MoveGenerationMixin`,
`HistoryManagerMixin`, `TurnManagerMixin`, `EndgameCheckerMixin`, and `RLMixin`.

- **Dual board representation:** a 2D array ([`board_manager.py`](DuckChess_Game/Logic/board_manager.py))
  for clarity, plus 64-bit bitboards ([`bitboard_manager.py`](DuckChess_Game/Logic/bitboard_manager.py))
  for fast move generation. [`game_state_validator.py`](DuckChess_Game/Logic/game_state_validator.py)
  keeps the two in sync.
- **RL bridge:** [`rl_mixin.py`](DuckChess_Game/Logic/rl_mixin.py) exposes a 19-channel observation
  ([`observation_encoder.py`](DuckChess_Game/Logic/observation_encoder.py)) and a 4096-action mask
  ([`action_masker.py`](DuckChess_Game/Logic/action_masker.py)) to the training environment.

### web_ui — the browser app
A FastAPI backend ([`server.py`](web_ui/server.py), port 7890) that loads every checkpoint under
`models/duck_ppo/` and serves a single-file frontend ([`index.html`](web_ui/index.html)). See
[docs/WEB_UI_SETUP.md](docs/WEB_UI_SETUP.md).

### SBThree — the RL pipeline
A Gymnasium environment wraps the engine; training uses `SubprocVecEnv` with parallel environments
and MaskablePPO. League-based and engine-based opponents drive a curriculum; `mcts.py` adds
AlphaZero-style search at inference. See [the next section](#the-reinforcement-learning-pipeline).

---

## The reinforcement-learning pipeline

The agent learns the game's quirks — especially **defensive duck placement** and the two-phase
turn. Full history is in [docs/training_log.md](docs/training_log.md), and the design rationale for
the current line of work is in [PLAN_V2.md](PLAN_V2.md). The short version:

| Concept | How it's modeled |
|---------|------------------|
| **Observation** | A `19 × 8 × 8` tensor: 12 piece planes + duck + en passant + castling + turn. |
| **Action space** | `4096` discrete actions (`64 × 64` from/to squares), with the duck phase reusing the same space. |
| **Action masking** | [`action_masker.py`](DuckChess_Game/Logic/action_masker.py) makes illegal actions unselectable — the policy never sees an invalid move. |
| **Curriculum** | Random → greedy → dense-reward mechanics → self-play → league → alpha-beta punisher → engine grounding vs **Peter** → the v2 opponent-pool run → the antiexploit_v2 corrective run. |
| **Reward** | Sparse terminal (+1 win / −1 loss / +0.1 draw) for league/v2 stages; dense shaping for older corrective runs. |
| **Inference search** | [`mcts.py`](DuckChess_Game/SBThree/mcts.py) — PUCT MCTS factored over piece + duck, using a distilled value head. The lesson: a value head *evaluates*, the policy *chooses* — only MCTS makes lookahead help. |
| **Ground truth** | [`eval_vs_peter.py`](DuckChess_Game/SBThree/eval_vs_peter.py) reports real W/L/D vs the Peter engine — the metric that revealed self-play models were weaker than they looked. |

**Run training** (the current line is the antiexploit_v2 → Expert-Iteration pipeline on branch
`antiexploit_v2`):

```bash
# Phase A: corrective policy run
python -m DuckChess_Game.SBThree.train_antiexploit_v2

# Phase B: Expert Iteration loop (MCTS self-play -> retrain policy+value -> eval -> repeat)
python -m DuckChess_Game.SBThree.run_exit

# Headless / background-safe Peter training (step tracking + resume)
python -m DuckChess_Game.SBThree.train_peter_headless --steps 10_000_000
```

See [docs/HEADLESS_TRAINING.md](docs/HEADLESS_TRAINING.md) for long, unattended runs (nohup, `pythonw`,
PowerShell jobs, `screen`), resuming from checkpoints, and TensorBoard monitoring.

**Standing result:** every model so far beats Peter depth-2 but scores **0 wins vs Peter depth-3**.
Cracking depth-3 is the goal of the Expert-Iteration loop.

---

## Testing

The canonical suite lives in [`tests/`](tests). The honest current state in the project `.venv`:

- **Engine + RL core:** ~332 tests, **330 pass, 2 fail**. The 2 failures are a stale hard-coded
  count in `test_env_factory.py` (it expects 17 registered envs; `antiexploit_v2` was added, making
  18) — not an engine defect.
- **Web-UI tests** (`test_web_ui_server.py`, `test_web_ui_integration.py`, `test_performance.py`):
  require `httpx`, which is in `requirements.txt` but not yet installed in the current `.venv`. Run
  `pip install -r requirements.txt` to enable them.
- **End-to-end + visual** (`test_e2e_*.py`, `test_visual_regression.py`): require Playwright
  browsers (`playwright install`).

```bash
pytest                              # full suite (testpaths=tests via pytest.ini)
pytest tests/test_rules_checker.py  # one module
pytest --cov=DuckChess_Game.Logic   # with coverage
```

Full details, the headless test setup, and troubleshooting are in
[docs/TESTING.md](docs/TESTING.md).

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12 |
| Web UI | FastAPI + Uvicorn, single-file HTML/JS |
| RL framework | Stable-Baselines3 + sb3-contrib (MaskablePPO) |
| RL environment | Gymnasium |
| Inference search | Custom PUCT MCTS (`mcts.py`) |
| Numerics / tensors | NumPy, PyTorch (CPU) |
| Testing | pytest, pytest-cov (web/e2e: httpx, Playwright) |
| Monitoring | TensorBoard |

---

## Documentation map

| Document | What it covers |
|----------|----------------|
| [README.md](README.md) | Project overview and quick start (this file) |
| [CLAUDE.md](CLAUDE.md) | Architecture and commands for AI coding assistants |
| [PLAN_V2.md](PLAN_V2.md) | The v2 + search + Expert-Iteration plan, results, and the central lesson |
| [docs/INDEX.md](docs/INDEX.md) | Index of everything under `docs/` |
| [docs/TESTING.md](docs/TESTING.md) | Running, reading, and extending the test suite |
| [docs/HEADLESS_TRAINING.md](docs/HEADLESS_TRAINING.md) | Long, unattended training runs |
| [docs/WEB_UI_SETUP.md](docs/WEB_UI_SETUP.md) | Setting up and running the web UI |
| [docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md) | Current build status at a glance |
| [docs/training_log.md](docs/training_log.md) | Stage-by-stage training history and results |
| [docs/STP-DUCK-001.md](docs/STP-DUCK-001.md) | Formal Software Test Plan |
| [docs/STD-DUCK-001.md](docs/STD-DUCK-001.md) | Formal Software Test Design |
