# The Game Engine — Logic Layer

## Files covered

```
DuckChess_Game/Logic/
  logic.py               ← hub class
  board_manager.py       ← 2D board initialization
  bitboard_manager.py    ← 64-bit integer boards (fast)
  move_generation.py     ← legal move calculator
  turn_manager.py        ← execute_move, place_duck, ai_turn
  endgame_checker.py     ← win/draw detection
  history_manager.py     ← undo / snapshot / replay
  observation_encoder.py ← board → 19×8×8 tensor
  action_masker.py       ← legal-only 4096 mask
  move_pipeline.py       ← atomic two-phase turn wrapper
  constants.py           ← PAWN, KNIGHT, KING, PIECE_VALUES …
```

---

## The mixin architecture — why it exists

`GameLogicMixin` in `logic.py` does not contain any game logic itself. It inherits from five mixin classes:

```python
class GameLogicMixin(
    MoveGenerationMixin,
    HistoryManagerMixin,
    TurnManagerMixin,
    EndgameCheckerMixin,
    RLMixin
):
```

**Why mixins instead of one big class?**

1. **Separation of concerns** — each file has one job. `EndgameCheckerMixin` knows nothing about rendering; `RLMixin` knows nothing about move history.
2. **Testability** — you can instantiate a class that only has `EndgameCheckerMixin` to unit-test win conditions without loading the full engine.
3. **The `_HeadlessEngine` trick** — for RL training, the code needs a game engine with zero Pygame dependency. `_HeadlessEngine` simply subclasses `GameLogicMixin` and sets `game_mode = 'rl_training'`. Every mixin already has guards like `if hasattr(self, 'play_sound')` or `if game_mode != 'replay'`, so the headless version works without any modification.

```python
class _HeadlessEngine(GameLogicMixin):
    def __init__(self):
        self.game_mode = 'rl_training'
        self.reset_game_state()
```

The desktop UI class (`DuckChess` in `main.py`) inherits from `GameLogicMixin` too, but also from `RenderingMixin`, `InputHandlerMixin`, etc. Same core logic, different outer shell.

---

## Dual board representation

The engine maintains **two synchronized representations of the board at all times**.

### 1. The 2D array (`self.board`)

```python
self.board[r][c]  # returns a Piece object or None
```

- Row 0 = top of the board (rank 8 from White's perspective)  
- Row 7 = bottom (rank 1)  
- Easy to read, easy to iterate for UI rendering and human-readable debugging  
- Slow for bulk operations — iterating all 64 squares in a loop is O(64)

### 2. Bitboards (`self.bb_mgr`)

A `BitboardManager` holds 13 Python integers, each representing one set of squares as a 64-bit bitmask:

```
piece_boards['w'][PAWN]    ← one int; bit i is set if white pawn is on square i
piece_boards['w'][KNIGHT]
... (6 white + 6 black piece boards)
duck_board                 ← one int for the duck
white_occupancy            ← OR of all white piece boards (cached)
black_occupancy            ← OR of all black piece boards (cached)
all_occupancy              ← white | black | duck
```

Square indexing: `sq = row * 8 + col`. Bit 0 = a8 (top-left), bit 63 = h1 (bottom-right) from the way the engine stores it.

**Why bitboards?**

The action masker needs to know every empty square for duck placement. With a bitboard this is one operation:

```python
valid_duck_squares = ~bb_mgr.all_occupancy & 0xFFFFFFFFFFFFFFFF
```

Instead of scanning all 64 squares, this is a single bitwise NOT. The result is a 64-bit number where each set bit is a valid duck destination.

Similarly, finding all white pieces is `white_occupancy` — you iterate only over set bits, not empty squares.

### Sync invariant

The two representations must always agree. `verify_sync()` in `BitboardManager` checks every square and every piece type. It is called every time a duck is placed (the end of every turn). If they ever drift, a critical warning is printed:

```python
if not self.bb_mgr.verify_sync(self.board, self.duck_pos):
    print("CRITICAL WARNING: The Bitboard engine is out of sync!")
```

If you ever see this during training or gameplay, something in `MoveExecutor` or a manual board edit failed to update both representations.

---

## Move generation — `MoveGenerationMixin`

`get_piece_legal_moves(r, c)` returns a list of `(row, col)` destinations for the piece at position `(r, c)`.

**How it works at a high level:**

1. Identify the piece type (pawn, knight, bishop, etc.)
2. Generate all *candidate* moves for that piece (sliding pieces use bitboard rays; knights use a fixed offset table)
3. Filter out moves that land on a friendly piece, the duck, or squares blocked by the duck
4. For pawns: add en passant, promotion triggers
5. Return the list

The move list is used by two consumers:
- **The UI** — to highlight which squares a clicked piece can move to
- **The action masker** — to build the 4096-element legal-move mask for the neural network

**Why no check filtering?**  
In standard chess, `get_legal_moves` must filter out moves that leave your own king in check. In Duck Chess there is no check — you win by king *capture* next turn. So the legal move generator is simpler and faster: it only needs to respect the duck's blocking and basic piece movement rules.

---

## The two-phase turn — `execute_move` and `place_duck`

### `execute_move(start, end, animated=False)`  ← `turn_manager.py:10`

1. Look up the piece at `start`
2. Detect whether this is a capture (including en passant), a castle, or a normal move
3. Delegate to `MoveExecutor.execute_piece_move()` which updates both the 2D board and the bitboards
4. Update `en_passant_target` (set for double pawn pushes, clear otherwise)
5. Update `half_move_clock` (reset on pawn/capture, increment otherwise)
6. **Check if a king was captured** — if yes, set `game_over = True` and return without entering the duck phase
7. Handle pawn promotion (auto-queen in RL/replay modes; UI shows a picker)
8. Set `self.phase = 'move_duck'` — the turn is now waiting for duck placement

### `place_duck(pos, animated=False)`  ← `turn_manager.py:129`

1. Validate: the target square must be empty AND not be where the duck currently sits
2. Update `bb_mgr.move_duck()` — clears old duck bit, sets new duck bit
3. Set `self.duck_pos = pos`, `self.phase = 'move_piece'`, flip `self.turn`
4. Run `verify_sync()` to assert both board representations agree
5. Call `check_game_end_conditions()` — this is where the Fowling rule and 50-move draw are checked

**Critical invariant:** The game state is never in an intermediate position. `execute_move` either completes its half of the turn or aborts entirely (if the piece is not found). `place_duck` completes the second half. Between them, `phase == 'move_duck'` is the "half-done" marker.

---

## `reset_game_state()` — what a fresh game looks like

Called in `__init__` and at the start of every RL episode:

```
self.board        ← fresh 8×8 array (standard chess opening position)
self.bb_mgr       ← fresh BitboardManager, synced to the 2D board
self.turn         = 'w'
self.phase        = 'move_piece'
self.duck_pos     = (-1, -1)   ← no duck yet (placed on first move's duck phase)
self.half_move_clock = 0
self.game_over    = False
self.winner       = None
```

Note that `duck_pos = (-1, -1)` means the duck has not been placed yet. The action masker uses `prev_duck_pos` to exclude the duck's current square from valid placements — on the very first duck placement, there is no previous position to exclude.

---

## FEN generation — `generate_fen()` in `BitboardManager`

The engine can serialize its state to a Duck-Chess-extended FEN string, used to pass positions to the external **Peter engine** (the alpha-beta opponent):

```
rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1 [d4]
```

The `[d4]` at the end is the duck position — an extension to standard FEN. This lets Peter's engine understand the full game state without any other communication protocol.
