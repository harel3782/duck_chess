# Software Test Design (STD) — Duck Chess Engine

**Document ID:** STD-DUCK-001
**Version:** 1.1
**Date:** 2026-06-10
**Linked STP:** STP-DUCK-001

---

## Introduction

This document specifies **20 critical test cases** that implement the strategy defined in
STP-DUCK-001. They are the highest-value, must-pass cases — the subset that gates checkpoint
promotion. They are a *representative slice* of the full implemented suite, which now contains
**277 tests** across 14 modules under `tests/` (see [TESTING.md](../TESTING.md)).

**Test identification scheme:** `TC-<MODULE>-<NNN>`

All cases are executable from the project root with:

```bash
pytest          # runs the full suite (pytest.ini sets testpaths = tests)
```

---

## Test Cases

| ID | Module | Preconditions | Test Steps | Expected Result | Pass Criteria |
|---|---|---|---|---|---|
| **TC-BB-001** | BitboardManager | Fresh empty BitboardManager | Call `set_bit(0, 0)` | `get_bit(result, 0)` is True; all other 63 bits are 0 | Single bit set at position 0 |
| **TC-BB-011** | BitboardManager | HeadlessEngine after `reset_game_state()` | Call `bb_mgr.verify_sync(board, duck_pos)` | Returns True | Bitboard synced with 2D board |
| **TC-RC-001** | RulesChecker | Standard starting board | `is_in_check('w', board, (-1,-1))` | Returns False | White not in check at start |
| **TC-RC-007** | RulesChecker | Rook-to-king ray with duck blocking | `is_in_check('w', board, (4,2))` with duck at (4,2) | Returns False | Duck blocks the rook ray |
| **TC-MG-001** | MoveGeneration | HeadlessEngine at starting position | Sum all white legal moves across all squares | Total = 20 | Exactly 20 opening moves |
| **TC-MG-007** | MoveGeneration | White rook on an open file, duck mid-file | `get_piece_legal_moves(rook_r, rook_c)` | Rook cannot reach squares beyond the duck | Duck blocks a sliding piece |
| **TC-MG-009** | MoveGeneration | White pawn moves (6,4) → (4,4) | Check `en_passant_target` and black's adjacent pawn moves | En passant capture square appears in legal moves | En passant target set correctly |
| **TC-MG-012** | MoveGeneration | Squares (7,5) and (7,6) cleared | `can_castle(7, 4, True)` | Returns True | Kingside castling available |
| **TC-AM-002** | ActionMasker | ActionMasker instance | For all 4096 pairs: `decode(encode(move))` | All 4096 pairs return the original coordinates | Full action-space roundtrip is bijective |
| **TC-AM-004** | ActionMasker | HeadlessEngine at start, phase='move_piece' | `get_valid_action_masks(...)` | `mask.sum() == 20` | Exactly 20 valid actions at start |
| **TC-OE-001** | ObservationEncoder | Starting position | `encode_state(...).shape` | `(19, 8, 8)` | Observation shape correct |
| **TC-OE-003** | ObservationEncoder | Starting position | `obs[0].sum()` (white pawns channel) | `8.0` | Channel 0 has exactly 8 ones |
| **TC-OE-014** | ObservationEncoder | turn = 'w' | `obs[14].sum()` (turn channel) | `64.0` (all ones) | Turn channel correctly encoded |
| **TC-EG-001** | EndgameChecker | Board with no legal moves for the current player | `check_game_end_conditions()` | `game_over = True`; `winner == self.turn` | **Fowling: the stuck color WINS** ⭐ |
| **TC-EG-002** | EndgameChecker | `half_move_clock = 100` | `check_game_end_conditions()` | `game_over = True`; `winner = 'draw'` | 50-move rule triggers a draw |
| **TC-MP-001** | MovePipeline | HeadlessEngine at start | `execute_full_turn((6,4),(4,4),(3,3))` | `result.ok = True`; turn = 'b'; duck at (3,3) | Full turn succeeds |
| **TC-MP-005** | MovePipeline | `engine.phase = 'move_duck'` (wrong phase) | `execute_full_turn((6,4),(4,4),(3,3))` | `result.ok = False`; board unchanged | Illegal move rejects with zero mutation |
| **TC-GV-001** | GameStateValidator | HeadlessEngine after reset | `GameStateValidator.full_check(engine)` | `report.ok = True`; no issues | Fresh engine passes validation |
| **TC-ENV-001** | RL Environment | BaseDuckChessEnv instantiated | `env.observation_space.shape` | `(19, 8, 8)` | Observation space shape correct |
| **TC-ENV-008** | RL Environment | No color randomization configured | 10× `env.reset()`, check `engine.turn` | All return 'w' | Consistent white start |

---

## Critical Notes

### ⭐ TC-EG-001: Fowling rule (highest priority)
This is the **defining rule of Duck Chess** and the inverse of standard chess:
- A player with **no legal moves WINS** (this is called "fowling"), not loses.
- Standard chess libraries reverse this winner logic, so testing must be deliberate. The engine
  sets `winner = self.turn` (the stuck color) in `endgame_checker.py`.

### TC-MP-005: Atomic execution
Illegal piece moves must produce **zero** state mutation. This is critical for RL training stability:
pre-validation prevents any partial update to the game state.

### TC-AM-002 & TC-AM-004: Action-space integrity
- The action space is always 4096 (8×8×8×8).
- The piece phase and the duck phase never collide.
- Every valid action encodes and decodes correctly (bijective roundtrip).

### TC-OE-* & TC-ENV-001: RL observation & interface
- 19-channel tensor (12 piece planes + duck + en passant + castling + turn).
- Shape and dtype must be exact for RL training stability.

### Win by king capture (companion invariant)
Beyond fowling, the game also ends the instant the king is captured, with the capturing color as
the winner (`turn_manager.py`). This is covered by move-pipeline and endgame tests in the full suite.

---

## Case-to-suite mapping

The critical cases above are implemented within these `tests/` modules:

| Module group | File(s) |
|--------------|---------|
| TC-BB-* | `tests/test_bitboard_manager.py` |
| TC-RC-* | `tests/test_rules_checker.py` |
| TC-MG-* | `tests/test_move_generation.py` |
| TC-AM-* | `tests/test_action_masker.py` |
| TC-OE-* | `tests/test_observation_encoder.py` |
| TC-EG-* | `tests/test_move_pipeline.py`, `tests/test_game_state_validator.py` |
| TC-MP-* | `tests/test_move_pipeline.py` |
| TC-GV-* | `tests/test_game_state_validator.py` |
| TC-ENV-* | `tests/test_env_base.py`, `tests/test_env_factory.py` |

---

## Test Execution

```bash
# From the project root
cd duck_chess

# Full suite (pytest.ini -> testpaths = tests)
pytest

# With coverage
pytest --cov=DuckChess_Game.Logic --cov-report=html

# A single critical module
pytest tests/test_move_pipeline.py -v
```

---

## Expected Output

A fully green run looks like:

```
=================== 277 passed in N.NNs ===================
```

All 20 critical cases above must pass before a Stage 12/13 checkpoint is promoted.

### Known issues (as of 2026-06-10)

The current run is **275 passed, 2 failed** (`277 collected`). Both failures are in
`tests/test_env_factory.py` (`test_returns_expected_stage_count` and
`test_has_expected_entry_count`): `EnvFactory.list_stages()` returns 16 entries while only 15 are
unique — a **duplicate key in the stage registry**, not an engine-logic defect. All 20 critical
cases in this STD pass. The duplicate-key fix is tracked separately; it does not block checkpoint
promotion, which gates on the engine and RL-interface cases.

---

**END OF STD-DUCK-001**
