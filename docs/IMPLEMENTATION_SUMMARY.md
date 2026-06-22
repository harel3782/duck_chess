# Implementation Summary

A snapshot of what is built in this repository and where it lives. For the full project tour see
[../README.md](../README.md); for stage-by-stage RL results see [training_log.md](training_log.md);
for the current line of work see [../PLAN_V2.md](../PLAN_V2.md).

---

## 1. Game engine — complete

Pure-Python engine under [`../DuckChess_Game/Logic/`](../DuckChess_Game/Logic), built with a mixin
composition pattern around the `GameLogicMixin` hub in
[`logic.py`](../DuckChess_Game/Logic/logic.py).

- Full Duck Chess rules: piece movement, castling, en passant, promotion, and **duck blocking**.
- **Inverted win conditions** vs standard chess:
  - Win by **capturing the king** ([`turn_manager.py`](../DuckChess_Game/Logic/turn_manager.py)) — no
    check/checkmate.
  - **Fowling** — a player with no legal moves *wins*
    ([`endgame_checker.py`](../DuckChess_Game/Logic/endgame_checker.py)).
  - The only draw is the **50-move rule** (100 half-moves).
- **Dual board representation:** a 2D array for clarity plus 64-bit bitboards for fast move
  generation, kept in sync and diagnosable via
  [`game_state_validator.py`](../DuckChess_Game/Logic/game_state_validator.py).
- **Atomic two-phase turns** ([`move_pipeline.py`](../DuckChess_Game/Logic/move_pipeline.py)): move a
  piece, then move the duck; an illegal move produces zero state mutation.

---

## 2. Front-ends — complete (two of them)

### Pygame desktop UI
Under [`../DuckChess_Game/UI/`](../DuckChess_Game/UI), entry point
[`main.py`](../DuckChess_Game/UI/main.py), composed from `GameLogicMixin` + rendering / input / asset
mixins.

- Game states: `menu`, `rules`, `edit`, `game`, each with split input and rendering modules.
- Move highlighting, animation, sound, an eval bar, promotion UI, and a game-over screen.
- **AI opponent:** loads `models/duck_ppo/v2/v2_value.zip` and plays it with `DuckMCTS` (200 sims).
  Set `model_path = None` to fall back to the simple alpha-beta AI, or `USE_MCTS = False` for the raw
  policy. (This is wired in by default now — older notes that say `model_path = None` are stale.)

### FastAPI web UI
Under [`../web_ui/`](../web_ui) — `server.py` (port 7890) + a single-file `index.html` frontend. It
auto-discovers every checkpoint under `models/duck_ppo/`, and supports human-vs-AI, 2-player local
play, save/load, and replay. See [WEB_UI_SETUP.md](WEB_UI_SETUP.md) and
[WEB_UI_IMPLEMENTATION_SUMMARY.md](WEB_UI_IMPLEMENTATION_SUMMARY.md).

---

## 3. Reinforcement-learning pipeline — complete; training ongoing

Pipeline under [`../DuckChess_Game/SBThree/`](../DuckChess_Game/SBThree), using Stable-Baselines3 +
sb3-contrib **MaskablePPO** over a Gymnasium environment, with **PUCT MCTS** for inference.

- **Observation:** 19×8×8 tensor (12 piece planes + duck + en passant + castling + turn).
- **Actions:** 4096-discrete (64×64), with strict legal-action masking
  ([`action_masker.py`](../DuckChess_Game/Logic/action_masker.py)).
- **Curriculum:** random → greedy → dense mechanics → self-play → league → alpha-beta punisher →
  engine grounding vs **Peter** → the v2 opponent-pool run → the antiexploit_v2 corrective run.
- **Inference search:** [`mcts.py`](../DuckChess_Game/SBThree/mcts.py) (AlphaZero-style PUCT,
  factored over piece + duck) and [`search.py`](../DuckChess_Game/SBThree/search.py) (alpha-beta).
  MCTS over a *distilled value head* is the configuration that actually improves play.
- **Expert Iteration (ExIt):** the current line of work —
  [`gen_mcts_data.py`](../DuckChess_Game/SBThree/gen_mcts_data.py) →
  [`train_exit.py`](../DuckChess_Game/SBThree/train_exit.py) →
  [`run_exit.py`](../DuckChess_Game/SBThree/run_exit.py).
- **Headless training:**
  [`train_peter_headless.py`](../DuckChess_Game/SBThree/train_peter_headless.py) runs background-safe
  with step tracking, CSV progress, and checkpoint resume (see
  [HEADLESS_TRAINING.md](HEADLESS_TRAINING.md)).
- **Ground-truth evaluation:**
  [`eval_vs_peter.py`](../DuckChess_Game/SBThree/eval_vs_peter.py) reports real W/L/D vs the engine;
  [`eval_antiexploit.py`](../DuckChess_Game/SBThree/eval_antiexploit.py) measures the three exploits
  directly.

Checkpoints live in [`../models/duck_ppo/`](../models/duck_ppo), organized by stage/run
(`stage 1`…`stage 14`, `peter_local`, `real`, `strong`, `antiexploit`, `v2`, `antiexploit_v2`).
Headline deliverables: `v2/v2_final.zip` (general policy, ~90–95% vs Peter d2, no exploit) and
`v2/v2_value.zip` (same policy + distilled value head — the search backbone wired into both UIs).

---

## 4. Testing — engine green; optional layers gated by deps

| Layer | Status |
|-------|--------|
| Engine + RL core (`tests/`, no extra deps) | **330 passed, 2 failed** — the 2 failures are a stale hard-coded env-count in `test_env_factory.py` (expects 17; `antiexploit_v2` made 18), not an engine defect |
| Web UI (`test_web_ui_*`, `test_performance.py`) | Error at collection until `pip install -r requirements.txt` (needs `httpx`) |
| E2E + visual (`test_e2e_*`, `test_visual_regression.py`) | Need Playwright browsers (`playwright install`) |
| Legacy smoke ([`test_logic.py`](../DuckChess_Game/Logic/test_logic.py)) | 26 tests, run explicitly (outside `testpaths`) |

Headless via the root [`conftest.py`](../conftest.py) (dummy SDL drivers). Formal artifacts — the
Software Test Plan and Software Test Design — are [STP-DUCK-001.md](STP-DUCK-001.md) and
[STD-DUCK-001.md](STD-DUCK-001.md). Full details: [TESTING.md](TESTING.md).

---

## 5. Documentation

| File | Purpose |
|------|---------|
| [../README.md](../README.md) | Project overview and quick start |
| [../CLAUDE.md](../CLAUDE.md) | Architecture and commands for AI assistants |
| [../PLAN_V2.md](../PLAN_V2.md) | v2 + search + Expert-Iteration plan, results, and lesson |
| [INDEX.md](INDEX.md) | Index of everything under `docs/` |
| [TESTING.md](TESTING.md) | Running and extending the test suite |
| [HEADLESS_TRAINING.md](HEADLESS_TRAINING.md) | Long, unattended training runs |
| [WEB_UI_SETUP.md](WEB_UI_SETUP.md) | Web-UI setup and troubleshooting |
| [training_log.md](training_log.md) | Stage-by-stage training history |
| [STP-DUCK-001.md](STP-DUCK-001.md) / [STD-DUCK-001.md](STD-DUCK-001.md) | Formal test plan & design |

---

## Current status

| Area | Status |
|------|--------|
| Game engine | ✅ Complete; engine/RL tests green |
| Pygame UI | ✅ Complete (v2_value + MCTS wired in) |
| Web UI | ✅ Complete |
| RL pipeline & tooling | ✅ Complete |
| Model strength vs Peter depth-2 | ✅ ~90–100% (v2 raw / + MCTS), no king-rush exploit |
| Model strength vs Peter depth-3 | ⏳ Open (0 wins) — the Expert-Iteration loop targets this |

### Quick commands
```bash
python DuckChess_Game/UI/main.py                              # desktop game
python -m uvicorn web_ui.server:app --port 7890              # web UI (http://localhost:7890)
pytest                                                        # tests (see TESTING.md)
python -m DuckChess_Game.SBThree.eval_vs_peter               # evaluate vs the Peter engine
python -m DuckChess_Game.SBThree.run_exit                    # Expert-Iteration training loop
```
