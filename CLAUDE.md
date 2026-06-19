# CLAUDE.md

Guidance for Claude Code (claude.ai/code) and other AI assistants working in this repository.

## Project overview

Duck Chess is a chess-variant AI project: a fully playable Duck Chess game (chess with a neutral
"duck" piece that acts as a movable blocker) with a Pygame UI and a reinforcement-learning agent
trained via MaskablePPO (Stable-Baselines3 + sb3-contrib).

The three rules that make this *not* standard chess — and that the engine enforces:

1. **The duck** — after every normal move the player also moves a neutral duck. It can't be
   captured, blocks any square it occupies, and may not stay on its current square. Every turn is
   therefore **two phases**: move a piece, then move the duck.
2. **Win by king capture** — there is no check/checkmate; you win by *capturing* the enemy king
   (`turn_manager.py`).
3. **Fowling** — a player with **no legal moves wins** (the inverse of stalemate), handled in
   `endgame_checker.py`. The only draw is the 50-move rule (100 half-moves).

## Environment

- **Python 3.12**, with a local `.venv/`.
- Dependencies are pinned in `requirements.txt` (`pip install -r requirements.txt`). Key
  packages: `pygame`, `numpy`, `torch` (CPU), `stable-baselines3`, `sb3-contrib`, `gymnasium`
  (engine/RL), plus `fastapi`, `uvicorn`, `pydantic` (web UI), and `pytest` (tests).
  `pygame` is **required even headless** — the engine imports it via `turn_manager.py`.
- Primary development platform is **Windows** (PowerShell), but the engine and training are
  cross-platform.

## Running the code

### Game UI
```bash
python DuckChess_Game/UI/main.py
```
The UI currently loads **no** RL model — `model_path = None` in `DuckChess_Game/UI/main.py`. This
is intentional (see the comment there): every checkpoint so far either loses to the real Peter
engine or only wins via a narrow king-rush exploit. To wire a model back in, set `model_path` to a
checkpoint under `models/duck_ppo/`; it is loaded with `MaskablePPO.load(...)`.

### Web UI

A FastAPI + vanilla-JS app under `web_ui/` (separate from the Pygame UI). Run from the
**project root**:
```bash
python -m uvicorn web_ui.server:app --port 7890   # then open http://127.0.0.1:7890
# or:  python web_ui/server.py
```
`web_ui/server.py` wraps the pygame-free `_HeadlessEngine` and loads MaskablePPO checkpoints on
CPU. The opponent list is auto-discovered by scanning `models/duck_ppo/**/*.zip`
(`discover_models()`); models load lazily and are cached. A turn is still two phases, mirrored by
the API: `/api/move-piece` then `/api/place-duck`, after which the model plays its full turn.

Endpoints: `GET /api/models`; `POST /api/new-game` (`model: null` ⇒ local 2-player),
`/api/legal-moves`, `/api/move-piece`, `/api/place-duck`, `/api/resign`, `/api/undo-move`,
`/api/save-game`; `GET /api/saved-games`, `GET /api/load-game/{filename}`; `POST /api/delete-game`.
Web game saves are JSON under `saved_replays/web/` (created on demand; git-ignored); replays store
a `{board, duck}` snapshot per half-move so the duck moves during review. It is a local dev server
with open login — use a real browser.

### RL training

```bash
# Stage 11 league self-play
python DuckChess_Game/SBThree/train.py train

# Against the local Peter engine, with GUI (4 envs)
python DuckChess_Game/SBThree/train.py train-peter

# Stage 12 (final league)
python DuckChess_Game/SBThree/train_stage12.py

# Stage 13 (Peter depth-2 + stage-12 league)
python DuckChess_Game/SBThree/train_stage13.py
```

`train.py` is a multi-mode runner. Its subcommands are `train`, `train-peter`, `play`
(model vs Peter, sequential games), and `parallel` (model vs Peter in parallel browsers).

**Headless Peter training** (no GUI, background-safe, step-tracked):
```bash
# Start fresh
python DuckChess_Game/SBThree/train_peter_headless.py --steps 10_000_000

# Resume from a checkpoint
python DuckChess_Game/SBThree/train_peter_headless.py --checkpoint models/duck_ppo/peter_headless/peter_v5.zip

# Auto-resume from the latest checkpoint
python DuckChess_Game/SBThree/train_peter_headless.py --auto-resume

# Show progress without running training
python DuckChess_Game/SBThree/train_peter_headless.py --show-progress
```

**Time-bounded corrective runs** (designed to break the king-rush exploit by training against a
king-defending opponent):
```bash
python DuckChess_Game/SBThree/train_strong.py        # 12h Peter + strong self-play
python DuckChess_Game/SBThree/train_real.py          # 14h dense-reward vs Peter depth-3
python DuckChess_Game/SBThree/train_antiexploit.py   # 1h probe vs Peter depth-3
```

### Evaluation
```bash
# Ground-truth W/L/D vs the Peter engine (the metric self-play lacked)
python DuckChess_Game/SBThree/eval_vs_peter.py

# Evaluate while recording replays
python DuckChess_Game/SBThree/eval_with_replays.py
```

### Testing
```bash
# Canonical suite (277 tests; pytest.ini sets testpaths=tests)
pytest

# A single module
pytest tests/test_rules_checker.py -v

# With coverage
pytest --cov=DuckChess_Game.Logic --cov-report=html

# Legacy smoke test (26 tests), outside the default testpaths
pytest DuckChess_Game/Logic/test_logic.py -v
```

### Monitoring training
```bash
# TensorBoard
tensorboard --logdir tensorboard_logs/

# Headless training progress (real-time)
tail -f logs/peter_training_progress.csv
# PowerShell: Get-Content logs/peter_training_progress.csv -Tail 10 -Wait
```

## Architecture

Three modules under `DuckChess_Game/`, each using a **mixin composition pattern** — a central
class inherits focused behaviour from several mixins.

### Logic (`DuckChess_Game/Logic/`)
Pure-Python game engine. `logic.py` is the hub, inheriting from `MoveGenerationMixin`,
`TurnManagerMixin`, `HistoryManagerMixin`, and `EndgameCheckerMixin`. Key abstractions:

- **Dual board representation:** a 2D array (`board_manager.py`) for UI/logic clarity, plus 64-bit
  bitboards (`bitboard_manager.py`, `bitboard_move_gen.py`) for fast move generation.
- **RL interface:** `rl_mixin.py` exposes observation encoding and action masking to the training
  environment. Observations are a **19-channel** tensor (12 piece planes + duck + en passant +
  castling + turn). Actions are a **4096**-discrete space (64×64 from/to coordinates).
- `action_masker.py` enforces legal-move-only training — never let the model select an invalid
  action.
- `move_pipeline.py` orchestrates the atomic two-phase turn; an illegal move produces **zero**
  state mutation. `game_state_validator.py` is a stateless board/phase diagnostic.

### UI (`DuckChess_Game/UI/`)
Pygame application. `main.py` is the entry point and composes `GameLogicMixin`, `RenderingMixin`,
`InputHandlerMixin`, and `AssetManagerMixin`.

- `settings.py` — all visual constants (colors, fonts, layout, timing). Edit here for UI tweaks.
- Game states: `menu`, `rules`, `editor`, `game`. Input and rendering are split per state
  (e.g. `input_game.py` vs `input_menu.py`; one `rendering_*.py` per surface).

### SBThree (`DuckChess_Game/SBThree/`)
RL training pipeline using Stable-Baselines3 + sb3-contrib MaskablePPO.

- Gymnasium environments per stage (`duck_env_stage1_random.py` … `duck_env_stage13.py`), built on
  the shared `base/` (env, mask strategy, opponent strategy, reward calculator).
- Training uses `SubprocVecEnv` with parallel environments (8 for league stages; 4 for Peter).
- **Curriculum:** league-based opponents (a mix of alpha-beta AI from `ai.py` and historical RL
  checkpoints) plus the real **Peter** engine (`peter_local.py`). Reward is sparse terminal for
  league stages and dense-shaped for corrective runs.
- Checkpoints save to `models/duck_ppo/`; TensorBoard logs to `tensorboard_logs/`.

## Key files

| File | Purpose |
|------|---------|
| `DuckChess_Game/Logic/logic.py` | Main game-logic hub — start here to understand game state |
| `DuckChess_Game/Logic/turn_manager.py` | Turn advance + king-capture win detection |
| `DuckChess_Game/Logic/endgame_checker.py` | Fowling rule + 50-move draw |
| `DuckChess_Game/Logic/rl_mixin.py` | Bridge between game engine and RL environments |
| `DuckChess_Game/Logic/observation_encoder.py` | Board → 19-channel tensor encoding |
| `DuckChess_Game/Logic/action_masker.py` | Legal-move mask for the 4096 action space |
| `DuckChess_Game/Logic/move_pipeline.py` | Atomic two-phase turn orchestration |
| `DuckChess_Game/UI/main.py` | Pygame entry point, model loading, game loop |
| `web_ui/server.py` | FastAPI web backend — model discovery, sessions, save/load/delete, replay snapshots |
| `web_ui/index.html` | Web UI frontend (board, model browser, 2-player, save/replay, timers) — all-in-one HTML/CSS/JS |
| `DuckChess_Game/SBThree/train.py` | Multi-mode training runner (train / train-peter / play / parallel) |
| `DuckChess_Game/SBThree/train_peter_headless.py` | Headless, step-tracked Peter training |
| `DuckChess_Game/SBThree/eval_vs_peter.py` | Ground-truth W/L/D vs the Peter engine |
| `DuckChess_Game/SBThree/peter_local.py` | Local Peter engine opponent integration |
| `tests/` | Canonical pytest suite (277 tests) |
| `DuckChess_Game/Logic/test_logic.py` | Legacy smoke test (26 tests) |
| `models/duck_ppo/` | Saved model checkpoints, by stage |
| `saved_replays/web/` | Web UI game saves (JSON; created on demand, git-ignored) |
| `docs/training_log.md` | Training history and stage-by-stage notes |
| `logs/`, `tensorboard_logs/` | Training CSV progress; TensorBoard event files |
| `requirements.txt` | Pinned Python dependencies |

## Working in this repo

- **Run the tests before and after changes to `DuckChess_Game/Logic/`.** The engine is the
  foundation everything else depends on; `pytest` is fast and headless.
- **Respect the inverted rules.** When touching endgame or win logic, remember: king capture wins,
  no-legal-moves *wins* (fowling), and the only draw is the 50-move rule. Standard chess intuition
  is misleading here.
- **Never let the RL agent see illegal actions.** Action masking is a correctness invariant, not an
  optimization — preserve it in any env or masking change.
- **Measure model strength against Peter, not just self-play.** Self-play numbers have historically
  overstated real strength; `eval_vs_peter.py` is the source of truth.
