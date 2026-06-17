# CLAUDE.md

Guidance for Claude Code (claude.ai/code) and other AI assistants working in this repository.
Everything here is verified against the current code — trust it over older notes, and if you
change something it describes, update this file in the same change.

## Project overview

Duck Chess is a chess-variant AI project with three parts:

1. **A pure-Python game engine** that enforces the Duck Chess rules (`DuckChess_Game/Logic/`).
2. **Two front-ends** — a Pygame desktop app (`DuckChess_Game/UI/`) and a FastAPI + HTML web app
   (`web_ui/`).
3. **A reinforcement-learning pipeline** that trains an agent with MaskablePPO and plays it with
   AlphaZero-style MCTS at inference (`DuckChess_Game/SBThree/`).

The three rules that make this *not* standard chess — and that the engine enforces:

1. **The duck** — after every normal move the player also moves a neutral duck. It can't be
   captured, it blocks any square it occupies, and it may not stay on its current square. Every turn
   is therefore **two phases**: move a piece, then move the duck.
2. **Win by king capture** — there is no check/checkmate; you win by *capturing* the enemy king
   (`turn_manager.py`).
3. **Fowling** — a player with **no legal moves wins** (the inverse of stalemate), handled in
   `endgame_checker.py`. The only draw is the 50-move rule (100 half-moves).

When you touch endgame or win logic, remember these are inverted — standard chess intuition will
mislead you.

## Environment

- **Python 3.12**, with a local `.venv/` (use `.venv\Scripts\python.exe` on Windows).
- Dependencies are pinned in **`requirements.txt`** (`pip install -r requirements.txt`). Key
  packages: `fastapi`, `uvicorn`, `pygame`, `numpy`, `torch` (CPU), `stable-baselines3`,
  `sb3-contrib`, `gymnasium`, `pytest`, `pytest-cov`. A GPU is **not** required.
- Primary development platform is **Windows** (PowerShell). The engine and training are
  cross-platform.
- **Known gap:** `requirements.txt` lists `httpx` and `playwright`, but the current `.venv` does
  **not** have `httpx` installed, so the web-UI and performance tests cannot collect (see Testing).
  Run `pip install -r requirements.txt` to close the gap.

## Running the code

Run SBThree scripts as **modules from the repo root** (`-m`) so package imports resolve. Examples
below use the venv interpreter.

### Desktop game UI

```bash
python DuckChess_Game/UI/main.py
```

The desktop UI **does** load an RL model now (this changed — older docs said `model_path = None`).
In `DuckChess_Game/UI/main.py`:

```python
model_path = "models/duck_ppo/v2/v2_value.zip"   # set to None -> falls back to alpha-beta ai.py
USE_MCTS   = True                                 # set to False -> raw policy, no search
self.rl_searcher = DuckMCTS(self.rl_model, sims=200, c_puct=1.5)
```

So the in-game AI = the `v2_value` policy driven by `DuckMCTS` (200 sims). Fallback chain:
`model_path=None` → `ai.py` alpha-beta; `USE_MCTS=False` → raw policy.

### Web UI (FastAPI)

```bash
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
# then open http://localhost:7890  (interactive API docs at /docs)
```

`web_ui/server.py` discovers and loads every `.zip` under `models/duck_ppo/` and serves
`web_ui/index.html` (a single-file frontend). See `docs/WEB_UI_SETUP.md`.

### RL training — current line of work

The active training line is the **antiexploit_v2 → Expert Iteration (ExIt)** pipeline on branch
`antiexploit_v2`. Read `PLAN_V2.md` for the full rationale.

```bash
# Phase A: corrective policy run (fixes opening repetition, weak duck placement, endgame collapse)
python -m DuckChess_Game.SBThree.train_antiexploit_v2

# Phase B: Expert Iteration loop (gen MCTS self-play -> retrain policy+value -> eval -> repeat)
python -m DuckChess_Game.SBThree.run_exit          # orchestrator
python -m DuckChess_Game.SBThree.gen_mcts_data     # data generator (used by run_exit)
python -m DuckChess_Game.SBThree.train_exit        # joint policy+value training step
```

`scripts/run_full_build.ps1` runs the whole unattended build (Phase A then ExIt) and writes its PID
to `logs/fullbuild.pid`; progress goes to `logs/antiexploit_v2_progress.csv` and
`logs/fullbuild_*.log`.

### RL training — earlier stages and corrective runs (still present, mostly historical)

```bash
python -m DuckChess_Game.SBThree.train_peter_v2          # v2: opponent-pool + random starts + sparse reward
python -m DuckChess_Game.SBThree.train_peter_headless    # headless, step-tracked, resumable Peter training
python DuckChess_Game/SBThree/train.py train             # legacy league self-play
python DuckChess_Game/SBThree/train.py train-peter       # legacy vs Peter, with GUI (4 envs)
python -m DuckChess_Game.SBThree.train_stage12           # stage-12 league
python -m DuckChess_Game.SBThree.train_stage13           # stage-13 (Peter d2 + stage-12 league)
python -m DuckChess_Game.SBThree.train_strong            # 12h corrective (Peter + strong self-play)
python -m DuckChess_Game.SBThree.train_real              # 14h dense-reward vs Peter depth-3
```

`train_peter_headless.py` also supports `--checkpoint`, `--auto-resume`, and `--show-progress`
(see `docs/HEADLESS_TRAINING.md`).

### Evaluation

```bash
python -m DuckChess_Game.SBThree.eval_vs_peter           # ground-truth W/L/D vs the Peter engine
python -m DuckChess_Game.SBThree.eval_antiexploit --model <ckpt>   # measures the 3 exploits directly
python -m DuckChess_Game.SBThree.eval_search --engine mcts --sims 200   # evaluate WITH MCTS search
python -m DuckChess_Game.SBThree.eval_anchors            # strength vs a fixed anchor set -> Elo
python -m DuckChess_Game.SBThree.eval_with_replays       # evaluate while recording replays
```

`eval_vs_peter.py` is the source of truth for strength — self-play numbers have historically
overstated it.

### Testing

```bash
pytest                                  # canonical suite (pytest.ini sets testpaths=tests)
pytest tests/test_rules_checker.py -v   # a single module
pytest --cov=DuckChess_Game.Logic --cov-report=html
pytest DuckChess_Game/Logic/test_logic.py -v   # legacy smoke test (26 tests, outside testpaths)
```

**Real status (verified):** `tests/` collects **400 tests**, but **3 files error at collection**
(`test_web_ui_server.py`, `test_web_ui_integration.py`, `test_performance.py`) because `httpx`
isn't installed. The engine + RL core (everything except the web/e2e/visual layers) runs **330
passed, 2 failed**. The 2 failures are stale: `test_env_factory.py` hard-codes 17 expected env
registry entries, but `antiexploit_v2` was added (now 18) — a test-count drift, **not** an engine
defect. The e2e (`test_e2e_*.py`) and `test_visual_regression.py` tests need Playwright browsers
(`playwright install`). Full details and how to run each layer: `docs/TESTING.md`.

### Monitoring training

```bash
tensorboard --logdir tensorboard_logs/
# PowerShell tail of the active build:
Get-Content logs/antiexploit_v2_progress.csv -Tail 10 -Wait
```

## Architecture

Three modules under `DuckChess_Game/`, plus `web_ui/`. Each Python module uses a **mixin
composition pattern** — a central class inherits focused behaviour from several mixins.

### Logic (`DuckChess_Game/Logic/`)
Pure-Python game engine. The hub class is **`GameLogicMixin`** in `logic.py`, which inherits:

| Mixin | Source file |
|-------|-------------|
| `MoveGenerationMixin` | `move_generation.py` |
| `HistoryManagerMixin` | `history_manager.py` |
| `TurnManagerMixin` | `turn_manager.py` |
| `EndgameCheckerMixin` | `endgame_checker.py` |
| `RLMixin` | `rl_mixin.py` |

Key abstractions:

- **Dual board representation:** a 2D array (`board_manager.py`) for UI/logic clarity, plus 64-bit
  bitboards (`bitboard_manager.py`, `bitboard_move_gen.py`) for fast move generation.
  `game_state_validator.py` is a stateless diagnostic that confirms the two stay in sync.
- **RL interface (`rl_mixin.py` + `observation_encoder.py` + `action_masker.py`):**
  - Observations are a **19-channel** `19×8×8` tensor: channels 0–11 piece planes (6 white + 6
    black), 12 duck, 13 en passant, 14 turn, 15–18 castling rights.
  - Actions are a **4096**-discrete space (`64×64` from→to squares); the duck phase reuses the same
    space. Encoding: `(sr*8+sc)*64 + (er*8+ec)`.
- `action_masker.py` enforces legal-move-only training. **Never let the model select an invalid
  action** — masking is a correctness invariant, not an optimization.
- `move_pipeline.py` orchestrates the atomic two-phase turn; an illegal move produces **zero** state
  mutation.

### UI (`DuckChess_Game/UI/`)
Pygame application. `main.py`'s `DuckChess` class composes `GameLogicMixin`, `RenderingMixin`,
`InputHandlerMixin`, and `AssetManagerMixin`.

- Game states: **`menu`, `rules`, `edit`, `game`** (the run loop checks `menu`/`rules`/`edit` and
  treats everything else as `game`). Input and rendering are split per state.
- `settings.py` — all visual constants (colors, fonts, layout, timing). Edit here for UI tweaks.

### web_ui (`web_ui/`)
A standalone FastAPI backend (`server.py`) + single-file HTML/JS frontend (`index.html`), port
**7890**. It loads all checkpoints from `models/duck_ppo/`, supports human-vs-AI and 2-player local
play, save/load, and replay. Independent from the desktop UI.

### SBThree (`DuckChess_Game/SBThree/`)
RL training pipeline using Stable-Baselines3 + sb3-contrib MaskablePPO.

- **Environments:** per-stage Gymnasium envs (`duck_env_stage1_random.py` …
  `duck_env_stage14_recovery.py`), the v2 pool env (`duck_env_v2.py`), and the current
  `duck_env_antiexploit_v2.py`, all built on the shared `base/` package (`env_base.py`,
  `mask_strategy.py`, `opponent_strategy.py`, `reward_calculator.py`). `env_factory.py` /
  `env_registry.py` wire stage names to configs.
- **Curriculum:** league-based opponents (alpha-beta AI from `ai.py` + historical RL checkpoints)
  plus the real **Peter** engine (`peter_local.py`). Reward is sparse terminal for league/v2 stages
  and dense-shaped for the older corrective runs.
- **Inference search:** `search.py` (alpha-beta over full turns incl. duck) and `mcts.py`
  (AlphaZero-style PUCT MCTS, factored over piece+duck). MCTS is the one that actually *helps* —
  see PLAN_V2.md.
- **Expert Iteration (ExIt):** `gen_mcts_data.py` (MCTS self-play → `(obs, π, z)` npz),
  `train_exit.py` (joint policy+value loss), `run_exit.py` (the gen→train→eval loop). Earlier,
  value-only distillation lives in `gen_value_data.py` + `finetune_value.py`.
- Training uses `SubprocVecEnv` with parallel environments. Checkpoints save to `models/duck_ppo/`;
  TensorBoard logs to `tensorboard_logs/`.

## Models — current deliverables

Checkpoints live under `models/duck_ppo/`, organized by stage/run:

| Path | What it is |
|------|------------|
| `v2/v2_final.zip` | The general v2 policy — beats Peter d2 ~90–95% with no king-rush exploit (Elo ~1025). |
| `v2/v2_value.zip` | Same policy + a distilled value head (sign-acc ~0.98). The search backbone; **wired into both UIs**. |
| `antiexploit_v2/ax_latest.zip` (+ `ax_v1..v3`) | Checkpoints from the current corrective run. (`ax_final.zip` and an `exit/exit_best.zip` are produced only when the full build completes.) |
| `real/`, `strong/`, `stage 1`…`stage 14`, `peter_local/`, `antiexploit/` | Earlier curriculum and corrective runs (historical). |
| `baseline_eval_snapshot.zip` | Frozen baseline used for v2 comparisons. |

The standing wall: every model so far beats Peter **depth-2** but scores **0 vs Peter depth-3**.
Cracking depth-3 is the goal of the ExIt loop (PLAN_V2.md Step 7b).

## Key files

| File | Purpose |
|------|---------|
| `DuckChess_Game/Logic/logic.py` | Game-logic hub (`GameLogicMixin`) — start here to understand game state |
| `DuckChess_Game/Logic/turn_manager.py` | Turn advance + king-capture win detection |
| `DuckChess_Game/Logic/endgame_checker.py` | Fowling rule + 50-move draw |
| `DuckChess_Game/Logic/rl_mixin.py` | Bridge between game engine and RL environments |
| `DuckChess_Game/Logic/observation_encoder.py` | Board → 19-channel tensor |
| `DuckChess_Game/Logic/action_masker.py` | Legal-move mask for the 4096 action space |
| `DuckChess_Game/Logic/move_pipeline.py` | Atomic two-phase turn orchestration |
| `DuckChess_Game/UI/main.py` | Desktop game entry point, model loading, game loop |
| `web_ui/server.py` | FastAPI web backend (model loading, game API) |
| `DuckChess_Game/SBThree/peter_local.py` | Local Peter engine opponent integration |
| `DuckChess_Game/SBThree/mcts.py` | AlphaZero-style PUCT MCTS (piece+duck) — the inference engine |
| `DuckChess_Game/SBThree/run_exit.py` | Expert-Iteration orchestrator (current line of work) |
| `DuckChess_Game/SBThree/train_antiexploit_v2.py` | Current corrective policy run |
| `DuckChess_Game/SBThree/eval_vs_peter.py` | Ground-truth W/L/D vs the Peter engine |
| `PLAN_V2.md` | The v2 + search + ExIt plan and its results (read for *why*) |
| `tests/` | Canonical pytest suite |
| `DuckChess_Game/Logic/test_logic.py` | Legacy smoke test (26 tests) |
| `docs/` | Testing docs, web-UI docs, headless-training guide, formal STP/STD |
| `docs/training_log.md` | Stage-by-stage training history and results |
| `models/duck_ppo/` | Saved model checkpoints, by stage/run |

## Working in this repo

- **Run the tests before and after changes to `DuckChess_Game/Logic/`.** The engine is the
  foundation everything else depends on; the engine/RL part of `pytest` is fast and headless.
- **Respect the inverted rules.** King capture wins, no-legal-moves *wins* (fowling), the only draw
  is the 50-move rule.
- **Never let the RL agent see illegal actions.** Action masking is a correctness invariant.
- **Measure model strength against Peter, not just self-play** (`eval_vs_peter.py`). For the three
  exploits specifically, use `eval_antiexploit.py`.
- **A value head EVALUATES; the policy CHOOSES.** Value-greedy / veto move-selection collapses play
  (0% vs d2). Only PUCT MCTS over a *distilled* value head makes lookahead help. This is the central
  lesson of PLAN_V2.md — don't reintroduce value-argmax move selection.
- Run SBThree scripts as modules (`-m DuckChess_Game.SBThree.<name>`) from the repo root.
