# Software Test Design (STD) — Duck Chess Engine

**Document ID:** STD-DUCK-001  
**Version:** 1.0  
**Date:** 2026-05-20  
**Linked STP:** STP-DUCK-001

---

## Introduction

This document specifies 20 critical test cases that implement the strategy defined in STP-DUCK-001. Test cases are executable with: `python -m pytest tests/ -v`

**Test Identification Scheme:** `TC-<MODULE>-<NNN>`

---

## Test Cases

| ID | Module | Preconditions | Test Steps | Expected Result | Pass Criteria |
|---|---|---|---|---|---|
| **TC-BB-001** | BitboardManager | Fresh empty BitboardManager | Call `set_bit(0, 0)` | `get_bit(result, 0)` is True; all other 63 bits are 0 | Single bit set at position 0 |
| **TC-BB-011** | BitboardManager | HeadlessEngine after `reset_game_state()` | Call `bb_mgr.verify_sync(board, duck_pos)` | Returns True | Bitboard synced with 2D board |
| **TC-RC-001** | RulesChecker | Standard starting board | `is_in_check('w', board, (-1,-1))` | Returns False | White not in check at start |
| **TC-RC-007** | RulesChecker | Rook-to-king ray with duck blocking | `is_in_check('w', board, (4,2))` where duck at (4,2) | Returns False | Duck blocks rook ray |
| **TC-MG-001** | MoveGeneration | HeadlessEngine at starting position | Sum all white legal moves across all squares | Total = 20 | Exactly 20 opening moves |
| **TC-MG-007** | MoveGeneration | White rook on open file with duck mid-file | `get_piece_legal_moves(rook_r, rook_c)` | Rook cannot reach squares beyond duck | Duck blocks sliding piece |
| **TC-MG-009** | MoveGeneration | White pawn moves (6,4) → (4,4) | Check `en_passant_target` and black adjacent pawn moves | En passant capture square appears in legal moves | En passant target set correctly |
| **TC-MG-012** | MoveGeneration | Squares (7,5) and (7,6) cleared | `can_castle(7, 4, True)` | Returns True | Kingside castling available |
| **TC-AM-002** | ActionMasker | ActionMasker instance | For all 4096 pairs: `decode(encode(move))` | All 4096 pairs return original coordinates | Full action space roundtrip bijective |
| **TC-AM-004** | ActionMasker | HeadlessEngine at start, phase='move_piece' | `get_valid_action_masks(...)` | `mask.sum() == 20` | Exactly 20 valid actions at start |
| **TC-OE-001** | ObservationEncoder | Starting position | `encode_state(...).shape` | `(19, 8, 8)` | Observation shape correct |
| **TC-OE-003** | ObservationEncoder | Starting position | `obs[0].sum()` (white pawns channel) | `8.0` | Channel 0 has exactly 8 ones |
| **TC-OE-014** | ObservationEncoder | turn = 'w' | `obs[14].sum()` (turn channel) | `64.0` (all ones) | Turn channel correctly encoded |
| **TC-EG-001** | EndgameChecker | Board with no legal moves for current player | `check_game_end_conditions()` | `game_over = True`; `winner == self.turn` | **Fowling: stalemate color WINS** ⭐ |
| **TC-EG-002** | EndgameChecker | `half_move_clock = 100` | `check_game_end_conditions()` | `game_over = True`; `winner = 'draw'` | 50-move rule triggers draw |
| **TC-MP-001** | MovePipeline | HeadlessEngine at start | `execute_full_turn((6,4),(4,4),(3,3))` | `result.ok = True`; turn = 'b'; duck at (3,3) | Full turn succeeds |
| **TC-MP-005** | MovePipeline | `engine.phase = 'move_duck'` (wrong phase) | `execute_full_turn((6,4),(4,4),(3,3))` | `result.ok = False`; board unchanged | Illegal move rejects with zero mutation |
| **TC-GV-001** | GameStateValidator | HeadlessEngine after reset | `GameStateValidator.full_check(engine)` | `report.ok = True`; no issues | Fresh engine passes validation |
| **TC-ENV-001** | RL Environment | BaseDuckChessEnv instantiated | `env.observation_space.shape` | `(19, 8, 8)` | Observation space shape correct |
| **TC-ENV-008** | RL Environment | No color randomization configured | 10× `env.reset()`, check `engine.turn` | All return 'w' | Consistent white start |

---

## Critical Notes

### ⭐ TC-EG-001: Fowling Rule (HIGHEST PRIORITY)
This is the **defining rule of Duck Chess** and differs fundamentally from standard chess:
- A player with **no legal moves WINS** (not loses)
- This is called "Fowling" in Duck Chess
- Standard chess libraries reverse the winner logic, so extreme care must be taken in testing

### TC-MP-005: Atomic Execution
Tests that illegal moves produce **zero state mutation**. This is critical for RL training:
- Pre-validation prevents state changes on invalid piece moves
- No partial updates to the game state

### TC-AM-002 & TC-AM-004: Action Space Integrity
- Action space is always 4096 (8×8×8×8)
- Piece phase and duck phase never collide
- All valid actions are encoded and decoded correctly

### TC-OE-* & TC-ENV-001: RL Observation & Interface
- 19-channel tensor (12 piece planes + duck + en passant + castling + turn)
- Shape and dtype must be exact for RL training stability

---

## Test Execution

```bash
cd c:\Users\harel\PycharmProjects\duck_chess

# Run all 20 test cases
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=DuckChess_Game/Logic

# Run specific test class
python -m pytest tests/test_endgame_checker.py::TestFowling -v
```

---

## Expected Output

```
======= 20 passed in 0.XXs =======
```

All tests must pass before Stage 12 checkpoint promotion.

---

**END OF STD-DUCK-001**
