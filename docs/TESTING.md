# Testing Guide

Duck Chess has a fast, headless test suite for the game engine and RL interface, plus optional
layers for the web UI and browser end-to-end flows. Tests are the safety net for the engine — the
layer everything else depends on — so run them before and after any change under
[`DuckChess_Game/Logic/`](../DuckChess_Game/Logic).

This is the single source of truth for testing. The numbers below were verified against the project
`.venv`; if you change the suite, update them here.

## The layers

| Layer | Files | Extra dependency | Default `pytest`? |
|-------|-------|------------------|-------------------|
| **Engine + RL core** | `test_bitboard_manager.py`, `test_rules_checker.py`, `test_move_generation.py`, `test_action_masker.py`, `test_observation_encoder.py`, `test_move_pipeline.py`, `test_game_state_validator.py`, `test_logic_comprehensive.py`, `test_env_base.py`, `test_env_factory.py`, `test_reward_calculator.py`, `test_opponent_strategy.py`, `test_peter_local.py`, `test_peter_opponent.py`, `test_peter_site_connector.py` | none | ✅ yes |
| **Web UI** | `test_web_ui_server.py`, `test_web_ui_integration.py`, `test_performance.py` | `httpx` (FastAPI `TestClient`) | collected, but **errors without `httpx`** |
| **End-to-end + visual** | `test_e2e_auth_and_menu.py`, `test_e2e_gameplay.py`, `test_e2e_save_replay.py`, `test_visual_regression.py` | Playwright browsers | collected, but needs `playwright install` |
| **Legacy smoke** | [`DuckChess_Game/Logic/test_logic.py`](../DuckChess_Game/Logic/test_logic.py) (26 tests) | none | ❌ outside `testpaths` — run explicitly |

`pytest.ini` sets `testpaths = tests`, so a bare `pytest` runs only the `tests/` directory (all four
non-legacy layers live there).

## Current status (verified)

Running the suite in the project `.venv`:

- **Engine + RL core: 330 passed, 2 failed** (~332 collected).
  - The **2 failures** are both in `tests/test_env_factory.py`
    (`test_has_expected_entry_count`, `test_returns_expected_stage_count`). They hard-code the
    expected number of registered environments at **17**, but `antiexploit_v2` was added to the
    registry, making **18**. This is a **stale test assertion**, not an engine defect — bump the
    expected count to 18 (or read it dynamically) to fix.
- **Web UI layer: 3 files error at collection** (`test_web_ui_server.py`,
  `test_web_ui_integration.py`, `test_performance.py`) with
  `RuntimeError: ... requires the httpx package`. `httpx` is in `requirements.txt` but is **not
  installed** in the current `.venv`. Fix: `pip install -r requirements.txt` (or `pip install httpx`).
- **E2E + visual layer:** collects but needs Playwright browsers installed (`playwright install`)
  and, for the integration paths, a reachable web server.

So the full `tests/` directory reports **400 collected, 3 errors** until `httpx` is installed.

## Running tests

```bash
# Default: the tests/ directory (pytest.ini -> testpaths = tests)
pytest

# Just the engine + RL core (fast, no extra deps) — what you run after touching Logic/
pytest tests/ \
  --ignore=tests/test_web_ui_server.py \
  --ignore=tests/test_web_ui_integration.py \
  --ignore=tests/test_performance.py \
  --ignore=tests/test_e2e_auth_and_menu.py \
  --ignore=tests/test_e2e_gameplay.py \
  --ignore=tests/test_e2e_save_replay.py \
  --ignore=tests/test_visual_regression.py

# A single module / class / test
pytest tests/test_rules_checker.py
pytest tests/test_rules_checker.py::TestKingProximityCheck

# With an HTML coverage report (opens htmlcov/index.html)
pytest --cov=DuckChess_Game.Logic --cov-report=html

# The legacy smoke test (not in the default testpaths)
pytest DuckChess_Game/Logic/test_logic.py -v
```

### Enabling the optional layers

```bash
pip install -r requirements.txt   # brings in httpx (web UI) and playwright
playwright install                # one-time: download browser binaries for e2e/visual tests
```

## What the engine + RL core covers

One file per concern:

| File | Module under test | Focus |
|------|-------------------|-------|
| `test_bitboard_manager.py` | `bitboard_manager.py` | Bit set/clear/get, 2D ↔ bitboard sync |
| `test_rules_checker.py` | `rules_checker.py` | Check/attack detection across all vectors, king proximity |
| `test_move_generation.py` | `move_generation.py` | Legal moves, duck blocking of sliders, castling, en passant |
| `test_action_masker.py` | `action_masker.py` | 4096-action encode/decode roundtrip, mask correctness |
| `test_observation_encoder.py` | `observation_encoder.py` | 19×8×8 tensor shape, channels, dtype |
| `test_move_pipeline.py` | `move_pipeline.py` | Atomic two-phase turn; illegal move → zero mutation |
| `test_game_state_validator.py` | `game_state_validator.py` | Stateless board/phase diagnostics |
| `test_logic_comprehensive.py` | `logic.py` end-to-end | Full-engine behaviour across rules |
| `test_env_base.py`, `test_env_factory.py` | `SBThree/base/`, `env_factory.py` | Gymnasium env contract, factory/registry wiring |
| `test_reward_calculator.py` | `base/reward_calculator.py` | Reward shaping logic |
| `test_opponent_strategy.py` | `base/opponent_strategy.py` | League opponent selection |
| `test_peter_local.py`, `test_peter_opponent.py`, `test_peter_site_connector.py` | Peter integration | Engine bindings, coordinate conversion, move sync |

### Rules under particular scrutiny

Duck Chess inverts several standard-chess expectations, so these have dedicated tests:

- **Fowling** — a player with no legal moves *wins*. The most counter-intuitive rule; see
  [`endgame_checker.py`](../DuckChess_Game/Logic/endgame_checker.py).
- **Win by king capture** — no checkmate; capturing the king ends the game.
- **Duck blocking** — the duck blocks sliding pieces and pawns, but knights jump it.
- **Atomic turns** — an illegal piece move must leave the board completely unchanged, which is
  critical for stable RL training.

The formal plan and case-by-case design are in [STP-DUCK-001.md](STP-DUCK-001.md) and
[STD-DUCK-001.md](STD-DUCK-001.md).

## Headless setup

Engine tests run without a display. The root [`conftest.py`](../conftest.py) sets dummy SDL drivers
before pygame imports, so the suite works on servers, in CI, and with the screen off:

```python
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
```

The engine is also exercised in `game_mode='rl_training'`, which auto-completes UI-only steps. No
GPU and no network access are required for the core layer — PyTorch CPU mode is sufficient.

## Continuous integration / pre-merge gate

After any change to [`DuckChess_Game/Logic/`](../DuckChess_Game/Logic), the engine + RL core must be
green before promoting a training checkpoint:

```bash
pytest --tb=short
```

## Validating a trained model

Testing the *engine* is unit-level. Validating a *trained model* is a separate, behavioural step:
play it against the real Peter engine and record ground-truth results.

```bash
# Ground-truth W/L/D vs the Peter engine
python -m DuckChess_Game.SBThree.eval_vs_peter

# Measure the three exploits (opening repetition, duck placement, endgame) directly
python -m DuckChess_Game.SBThree.eval_antiexploit --model <checkpoint>
```

Self-play scores have historically overstated real strength, so `eval_vs_peter.py` is the metric
that matters. For long training jobs and reading their CSV/TensorBoard progress, see
[HEADLESS_TRAINING.md](HEADLESS_TRAINING.md).

## Troubleshooting

**`RuntimeError: ... requires the httpx package`** — the web-UI tests need `httpx`. Run
`pip install -r requirements.txt`.

**E2E tests fail with a browser/launch error** — install Playwright browsers with
`playwright install`.

**`ModuleNotFoundError` / import errors** — `pythonpath = .` in `pytest.ini` adds the repo root to
`sys.path`. Run `pytest` from the repo root (not from inside `tests/`) with the `.venv` activated.

**pygame complains about a display** — the headless drivers are set in `conftest.py`. If you run a
test file directly with `python` instead of `pytest`, set `SDL_VIDEODRIVER=dummy` yourself first.

**A Peter test fails or hangs** — the Peter tests depend on the local engine bindings. Confirm the
engine imports cleanly, then re-run just that module: `pytest tests/test_peter_local.py -v`.

**Slow first collection** — the first run imports torch and pygame, which is most of the time.
Subsequent runs are faster; narrow to one module while iterating.
