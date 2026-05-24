# Software Test Plan (STP) — Duck Chess Engine

**Document ID:** STP-DUCK-001  
**Version:** 1.0  
**Date:** 2026-05-20  
**Project:** Duck Chess — Game Engine & Reinforcement Learning Pipeline

---

## 1. Introduction

### 1.1 Purpose
This document defines the test plan for the Duck Chess game engine and RL training pipeline. It specifies what is tested, how it is tested, and what constitutes acceptable quality before promotion to production checkpoints.

### 1.2 Scope
The plan covers the pure Python game engine (`DuckChess_Game/Logic/`), the RL interface layer, and the atomic turn pipeline. The Pygame UI layer and SBThree training scripts are **out of scope**.

### 1.3 Objectives
- Confirm correct implementation of all Duck Chess rules (fowling, duck blocking, en passant, castling)
- Verify correctness of the RL observation tensor (19 × 8 × 8) and action mask (4096-dimensional)
- Confirm 2D board and bitboard representations remain in sync
- Verify atomic turn execution: illegal moves produce zero state mutation
- Establish a regression baseline for further training stages

### 1.4 References
- `CLAUDE.md` — Project documentation
- `DuckChess_Game/Logic/logic.py` — Game engine hub
- `tests/conftest.py` — Test configuration
- `pytest.ini` — Pytest settings

### 1.5 Assumptions
- All tests run with Python 3.12 in the `.venv` virtual environment
- Tests execute in headless mode (`game_mode='rl_training'`)
- No GPU is required; PyTorch CPU mode is sufficient
- No network access required

---

## 2. Test Items

| ID | Module | File | Description |
|----|--------|------|-------------|
| TI-01 | BitboardManager | `Logic/bitboard_manager.py` | 64-bit board representation, occupancy tracking |
| TI-02 | BitboardMoveGen | `Logic/bitboard_move_gen.py` | Fast bitwise move generation |
| TI-03 | RulesChecker | `Logic/rules_checker.py` | Check detection (5 attack vectors) |
| TI-04 | MoveGeneration | `Logic/move_generation.py` | Legal move generation, castling, en passant |
| TI-05 | ActionMasker | `Logic/action_masker.py` | 4096-action encoding and masking |
| TI-06 | ObservationEncoder | `Logic/observation_encoder.py` | 19×8×8 state tensor encoding |
| TI-07 | EndgameChecker | `Logic/endgame_checker.py` | Fowling rule, 50-move rule, material score |
| TI-08 | MovePipeline | `Logic/move_pipeline.py` | Atomic two-phase turn orchestration |
| TI-09 | GameStateValidator | `Logic/game_state_validator.py` | Stateless board/phase diagnostic |
| TI-10 | BaseDuckChessEnv | `SBThree/base/` | Gymnasium RL environment wrapper |

---

## 3. Features to be Tested

| Feature | Priority |
|---------|----------|
| Bitboard bit operations (set, clear, get) | High |
| Coordinate-to-square mapping | High |
| 2D ↔ bitboard synchronization | High |
| Legal move count at start (20 moves) | High |
| Pawn double-push and blocking | High |
| Duck blocking of sliding pieces | High |
| Duck non-blocking of knights | High |
| En passant legality and blocking | High |
| Castling path validation | High |
| Check detection (all 5 vectors) | High |
| **Fowling rule (stalemate = win)** | **High** |
| 50-move rule | Medium |
| Action encoding/decoding roundtrip | High |
| Observation shape and channels | High |
| Atomic turn rejection (no state mutation) | High |
| Duck placement validation | High |

---

## 4. Features NOT to be Tested

| Feature | Reason |
|---------|--------|
| Pygame UI rendering | Requires display server |
| MaskablePPO training convergence | Statistical outcome, not deterministic |
| TensorBoard logging | Infrastructure concern |
| Save file format | Stable; out of scope |

---

## 5. Test Strategy & Approach

### 5.1 Unit Testing
All pure-logic classes are tested in isolation using `pytest` with `conftest.py` fixtures. Each test is stateless and fresh.

### 5.2 Integration Testing
Full end-to-end scenarios: piece move → duck placement → turn advance.

### 5.3 Regression Testing
The test suite runs as a pre-merge gate on the `master` branch. All tests must pass before checkpoint promotion.

### 5.4 Boundary & Edge-Case Testing
- Board corners: `(0,0)`, `(0,7)`, `(7,0)`, `(7,7)`
- Sentinel values: `duck_pos = (-1, -1)`, `en_passant_target = None`
- Out-of-bounds coordinates

### 5.5 Property Testing (Roundtrip)
All 4096 encode → decode pairs are verified as bijective.

---

## 6. Pass / Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Test suite execution | All tests pass | Any test fails |
| Starting position moves | Exactly 20 per color | Any other count |
| Action encoding roundtrip | All 4096 pairs bijective | Any mismatch |
| Observation tensor | Shape (19,8,8), dtype float32 | Wrong shape/dtype |
| Illegal move state mutation | Zero state change | Any state change |
| Fowling winner | `winner == self.turn` (stalemate color) | Any other assignment |
| Board sync at start | `verify_sync()` returns True | Returns False |

---

## 7. Test Deliverables

| Deliverable | Tool | Location |
|-------------|------|----------|
| Test results | `pytest -v` | CI / terminal |
| Coverage report | `pytest --cov` | `htmlcov/` |
| Test source | Python | `tests/` |
| STP document | Markdown | `docs/STP-DUCK-001.md` |
| STD document | Markdown | `docs/STD-DUCK-001.md` |

---

## 8. Environmental Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.12 |
| pytest | >=7.0 |
| pytest-cov | >=4.0 |
| numpy | Latest |
| stable-baselines3 | Latest |
| torch | CPU mode |
| OS | Windows 11 / Linux |

**Execution:** `python -m pytest tests/ -v`

---

## 9. Responsibilities

| Role | Name | Responsibility |
|------|------|-----------------|
| Developer/Tester | harel3782 | Write tests, fix failures, approve checkpoints |
| AI Pair Programmer | Claude Sonnet 4.6 | Test design, documentation |

---

## 10. Schedule

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Unit tests: Logic module | 2026-05-20 | Complete |
| Integration: full turn pipeline | 2026-05-20 | Complete |
| RL env: observation + mask tests | 2026-05-20 | Complete |
| Stage 12 training gate | Post-25 ckpts | In progress |
| Coverage target: 80%+ | TBD | Pending |

---

## 11. Risks & Contingencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Bitboard desync silent failure | Medium | High | `verify_sync()` after every `place_duck()` |
| Fowling rule misimplemented | Low | Critical | Dedicated test case asserting `winner == stalemate_color` |
| Promotion blocking duck phase | Medium | Medium | Test auto-complete in `rl_training` mode |
| ATOMIC_FAILURE partial state | Medium | High | Test suite verifies no mutation on rejection |
| Stage 12 wrong checkpoint | Fixed | Low | Fixed in `train_stage12.py`: numeric sort |

---

**END OF STP-DUCK-001**
