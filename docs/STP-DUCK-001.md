# Software Test Plan (STP) — Duck Chess Engine

**Document ID:** STP-DUCK-001
**Version:** 1.1
**Date:** 2026-06-10
**Project:** Duck Chess — Game Engine & Reinforcement Learning Pipeline
**Linked STD:** STD-DUCK-001

---

## 1. Introduction

### 1.1 Purpose
This document defines the test plan for the Duck Chess game engine and RL training pipeline. It
specifies *what* is tested, *how* it is tested, and what constitutes acceptable quality before a
training checkpoint is promoted.

### 1.2 Scope
The plan covers the pure-Python game engine (`DuckChess_Game/Logic/`), the RL interface layer
(observation encoding and action masking), the atomic turn pipeline, and the Peter engine opponent
integration. The Pygame UI rendering layer and the SBThree training *scripts* are **out of scope**
(the RL *environment contract* is in scope).

### 1.3 Objectives
- Confirm correct implementation of all Duck Chess rules: **fowling** (no legal moves wins),
  **win by king capture**, duck blocking, en passant, castling, and the 50-move draw.
- Verify the RL observation tensor (19 × 8 × 8) and action mask (4096-dimensional).
- Confirm the 2D board and bitboard representations stay in sync.
- Verify atomic turn execution: an illegal move produces zero state mutation.
- Verify the Peter opponent bindings and coordinate conversion.
- Establish a regression baseline for further training stages.

### 1.4 References
- `README.md`, `CLAUDE.md` — project documentation
- `DuckChess_Game/Logic/logic.py` — game-engine hub
- `tests/conftest.py` and root `conftest.py` — test configuration (headless setup)
- `pytest.ini` — pytest settings (`testpaths = tests`)
- `STD-DUCK-001.md` — companion Software Test Design

### 1.5 Assumptions
- Tests run with **Python 3.12** in the project `.venv`.
- Tests execute in headless mode (`game_mode='rl_training'`; dummy SDL drivers).
- No GPU is required; PyTorch CPU mode is sufficient.
- No network access is required.

---

## 2. Test Items

| ID | Module | File | Description |
|----|--------|------|-------------|
| TI-01 | BitboardManager | `Logic/bitboard_manager.py` | 64-bit board representation, occupancy tracking |
| TI-02 | BitboardMoveGen | `Logic/bitboard_move_gen.py` | Fast bitwise move generation |
| TI-03 | RulesChecker | `Logic/rules_checker.py` | Attack/check detection (all vectors), king proximity |
| TI-04 | MoveGeneration | `Logic/move_generation.py` | Legal move generation, castling, en passant, duck blocking |
| TI-05 | ActionMasker | `Logic/action_masker.py` | 4096-action encoding and masking |
| TI-06 | ObservationEncoder | `Logic/observation_encoder.py` | 19×8×8 state tensor encoding |
| TI-07 | EndgameChecker | `Logic/endgame_checker.py` | Fowling rule, 50-move rule, material score |
| TI-08 | MovePipeline | `Logic/move_pipeline.py` | Atomic two-phase turn orchestration |
| TI-09 | GameStateValidator | `Logic/game_state_validator.py` | Stateless board/phase diagnostic |
| TI-10 | BaseDuckChessEnv | `SBThree/base/` | Gymnasium RL environment wrapper |
| TI-11 | EnvFactory | `SBThree/env_factory.py` | Environment construction and wiring |
| TI-12 | Peter integration | `SBThree/peter_local.py`, `Logic/peter_opponent.py` | Engine bindings, coordinate conversion, move sync |

---

## 3. Features to be Tested

| Feature | Priority |
|---------|----------|
| Bitboard bit operations (set, clear, get) | High |
| 2D ↔ bitboard synchronization | High |
| Legal move count at start (20 moves) | High |
| Pawn double-push and blocking | High |
| Duck blocking of sliding pieces | High |
| Duck non-blocking of knights | High |
| En passant legality and blocking | High |
| Castling path validation | High |
| Check/attack detection (all vectors) | High |
| **Fowling rule (no legal moves = win)** | **High** |
| **Win by king capture** | **High** |
| 50-move rule | Medium |
| Action encoding/decoding roundtrip (4096) | High |
| Observation shape, channels, dtype | High |
| Atomic turn rejection (no state mutation) | High |
| Duck placement validation | High |
| Peter coordinate conversion & move sync | High |

---

## 4. Features NOT to be Tested

| Feature | Reason |
|---------|--------|
| Pygame UI rendering | Requires a display server; visual, not deterministic |
| MaskablePPO training convergence | Statistical outcome, not a unit-test concern |
| TensorBoard / CSV logging | Infrastructure concern |
| Save-file format | Stable; out of scope |

---

## 5. Test Strategy & Approach

### 5.1 Unit testing
Pure-logic classes are tested in isolation with `pytest` and `conftest.py` fixtures. Each test is
stateless and starts from a fresh engine.

### 5.2 Integration testing
End-to-end scenarios: piece move → duck placement → turn advance, plus a full game against the
Peter opponent.

### 5.3 Regression testing
The suite is the pre-merge gate on `master`. All tests must pass before checkpoint promotion.

### 5.4 Boundary & edge-case testing
- Board corners: `(0,0)`, `(0,7)`, `(7,0)`, `(7,7)`
- Sentinel values: `duck_pos = (-1,-1)`, `en_passant_target = None`
- Out-of-bounds coordinates

### 5.5 Property testing (roundtrip)
All 4096 `encode → decode` action pairs are verified as bijective.

---

## 6. Pass / Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Test suite execution | All tests pass | Any test fails |
| Starting-position moves | Exactly 20 per color | Any other count |
| Action encoding roundtrip | All 4096 pairs bijective | Any mismatch |
| Observation tensor | Shape (19,8,8), dtype float32 | Wrong shape/dtype |
| Illegal-move mutation | Zero state change | Any state change |
| Fowling winner | `winner == self.turn` (stuck color) | Any other assignment |
| King-capture winner | Capturing color wins immediately | Wrong/no winner |
| Board sync at start | `verify_sync()` returns True | Returns False |

---

## 7. Test Deliverables

| Deliverable | Tool | Location |
|-------------|------|----------|
| Test results | `pytest` | CI / terminal |
| Coverage report | `pytest --cov` | `htmlcov/` |
| Test source | Python | `tests/` |
| STP document | Markdown | `docs/STP-DUCK-001.md` |
| STD document | Markdown | `docs/STD-DUCK-001.md` |

---

## 8. Environmental Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.12 |
| pytest | >= 7.0 |
| pytest-cov | >= 4.0 |
| numpy | 2.x |
| stable-baselines3 / sb3-contrib | 2.8 |
| gymnasium | 1.2 |
| torch | CPU mode |
| OS | Windows 11 / Linux |

**Execution** (from the project root; `pytest.ini` sets `testpaths = tests`):

```bash
pytest                 # full suite
pytest --cov=DuckChess_Game.Logic --cov-report=html
```

---

## 9. Responsibilities

| Role | Responsibility |
|------|----------------|
| Developer / Tester | Write tests, fix failures, approve checkpoint promotions |
| AI pair programmer (Claude Code) | Test design, documentation, review |

---

## 10. Schedule

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Unit tests: Logic module | 2026-05-20 | Complete |
| Integration: full turn pipeline | 2026-05-20 | Complete |
| RL env: observation + mask tests | 2026-05-20 | Complete |
| Peter integration tests | 2026-06-10 | Complete |
| Suite expansion to per-module engine + RL coverage | 2026-06-10 | Complete |
| Coverage target: 80%+ | TBD | In progress |

---

## 11. Risks & Contingencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Bitboard desync (silent) | Medium | High | `verify_sync()` after every `place_duck()`; dedicated tests |
| Fowling rule misimplemented | Low | Critical | Dedicated test asserting `winner == stuck color` |
| King-capture win missed | Low | Critical | Dedicated test asserting capturing color wins immediately |
| Atomic-failure partial state | Medium | High | Suite verifies zero mutation on rejected moves |
| Peter coordinate-system mismatch | Medium | High | Conversion tests (Peter a1=0 vs engine indexing) |
| Wrong checkpoint promoted | Low | Low | Numeric sort in `train_stage12.py`; eval gate vs Peter |

---

**END OF STP-DUCK-001**
