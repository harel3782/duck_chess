# Testing Guide

Duck Chess ships with a fast, headless test suite that covers the game engine and the
reinforcement-learning interface. Tests are the safety net for the engine — the layer everything
else depends on — so run them before and after any change under `DuckChess_Game/Logic/`.

## The two test sets

| Location | Tests | Role |
|----------|-------|------|
| [`tests/`](tests) | **277** | **Canonical suite.** Per-module coverage of the engine and RL bridge. This is what `pytest` runs by default. |
| [`DuckChess_Game/Logic/test_logic.py`](DuckChess_Game/Logic/test_logic.py) | 26 | **Legacy smoke test.** Coarse "does it import and behave" checks. Lives outside the default `testpaths`, so run it explicitly. |

> **Current status:** `277 collected — 275 passed, 2 failed`. The two failures are in
> `tests/test_env_factory.py` (stage-registry count) — `EnvFactory.list_stages()` exposes a
> duplicate key, so it returns 16 entries where 15 are unique. This is a registry bug, not an
> engine-logic defect; the engine and RL-interface tests are all green.

The suite is configured by [`pytest.ini`](pytest.ini):

```ini
[pytest]
testpaths = tests
pythonpath = .
python_files = test_*.py
addopts = -v --tb=short
```

Because `testpaths = tests`, a bare `pytest` runs only the canonical suite.

## Running tests

```bash
# Canonical suite (277 tests)
pytest

# A single module
pytest tests/test_rules_checker.py

# A single class or test
pytest tests/test_rules_checker.py::TestKingProximityCheck
pytest tests/test_rules_checker.py::TestKingProximityCheck::test_kings_adjacent_gives_check

# With an HTML coverage report (opens htmlcov/index.html)
pytest --cov=DuckChess_Game.Logic --cov-report=html

# The legacy smoke test (not in the default testpaths)
pytest DuckChess_Game/Logic/test_logic.py -v
```

### Installing test dependencies

```bash
pip install pytest pytest-cov
```

## What the canonical suite covers

The 277 tests in `tests/` are organized one file per engine concern:

| File | Module under test | Focus |
|------|-------------------|-------|
| `test_bitboard_manager.py` | `bitboard_manager.py` | Bit set/clear/get, 2D ↔ bitboard sync |
| `test_rules_checker.py` | `rules_checker.py` | Check/attack detection across all attack vectors, king proximity |
| `test_move_generation.py` | `move_generation.py` | Legal moves, duck blocking of sliders, castling, en passant |
| `test_action_masker.py` | `action_masker.py` | 4096-action encode/decode roundtrip, mask correctness |
| `test_observation_encoder.py` | `observation_encoder.py` | 19×8×8 tensor shape, channels, dtype |
| `test_move_pipeline.py` | `move_pipeline.py` | Atomic two-phase turn; illegal move → zero mutation |
| `test_game_state_validator.py` | `game_state_validator.py` | Stateless board/phase diagnostics |
| `test_env_base.py` / `test_env_factory.py` | `SBThree/base/`, `env_factory.py` | Gymnasium env contract, factory wiring |
| `test_reward_calculator.py` | `base/reward_calculator.py` | Reward shaping logic |
| `test_opponent_strategy.py` | `base/opponent_strategy.py` | League opponent selection |
| `test_peter_local.py` / `test_peter_opponent.py` / `test_peter_site_connector.py` | Peter integration | Engine bindings, coordinate conversion, move sync |

### Rules under particular scrutiny

Duck Chess inverts several standard-chess expectations, so these have dedicated tests:

- **Fowling** — a player with no legal moves *wins*. The most important and most
  counter-intuitive rule; see [`endgame_checker.py`](DuckChess_Game/Logic/endgame_checker.py).
- **Win by king capture** — there is no checkmate; capturing the king ends the game.
- **Duck blocking** — the duck blocks sliding pieces (and pawns) but knights jump it.
- **Atomic turns** — an illegal piece move must leave the board completely unchanged, which is
  critical for stable RL training.

The formal test plan and case-by-case design are in
[docs/STP-DUCK-001.md](docs/STP-DUCK-001.md) and [docs/STD-DUCK-001.md](docs/STD-DUCK-001.md).

## Headless setup

Tests run without a display. The root [`conftest.py`](conftest.py) sets dummy SDL drivers before
pygame imports, so the suite works on servers, in CI, and with the screen off:

```python
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
```

The engine is also exercised in `game_mode='rl_training'`, which auto-completes UI-only steps. No
GPU and no network access are required — PyTorch CPU mode is sufficient.

## Continuous integration

The suite is the pre-merge gate on `master`. After any change to `DuckChess_Game/Logic/`:

```bash
pytest --tb=short
```

All tests must pass before promoting a training checkpoint.

## Validating training

Testing the *engine* is unit-level. Validating a *trained model* is a separate, behavioural step:
play it against the real Peter engine and record ground-truth results.

```bash
# Ground-truth W/L/D vs the Peter engine
python DuckChess_Game/SBThree/eval_vs_peter.py
```

This is the metric that matters — self-play scores have historically overstated real strength.
For running long training jobs (and reading their CSV/TensorBoard progress), see
[HEADLESS_TRAINING.md](HEADLESS_TRAINING.md).

## Troubleshooting

**`ModuleNotFoundError` / import errors**
`pythonpath = .` in `pytest.ini` adds the project root to `sys.path`. Run `pytest` from the repo
root (not from inside `tests/`), and make sure the `.venv` is activated.

**pygame complains about a display**
The headless drivers are set in `conftest.py`. If you run a test file directly with `python`
instead of `pytest`, set `SDL_VIDEODRIVER=dummy` yourself first.

**A Peter test fails or hangs**
The Peter tests depend on the local engine bindings. Confirm the engine imports cleanly, then
re-run just that module: `pytest tests/test_peter_local.py -v`.

**Slow collection**
First-run collection imports torch and pygame, which is the bulk of the time. Subsequent runs are
faster; narrow to one module while iterating.
