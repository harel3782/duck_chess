# Observation Tensor and Action Space

## File: `DuckChess_Game/Logic/observation_encoder.py` and `action_masker.py`

These two files define the interface between the game engine and the neural network.  
They answer: *what does the network see?* and *what can it choose?*

---

## The observation tensor — 19 × 8 × 8

The entire game state is encoded as a NumPy float32 array of shape `(19, 8, 8)`.  
Think of it as 19 "layers" stacked on top of the chessboard, each layer encoding one type of information.

```python
obs = np.zeros((19, 8, 8), dtype=np.float32)
```

Values are either `0.0` or `1.0` — every channel is a binary board.

---

### Channels 0–5 — White pieces

| Channel | Piece type |
|---------|-----------|
| 0 | White Pawns |
| 1 | White Knights |
| 2 | White Bishops |
| 3 | White Rooks |
| 4 | White Queens |
| 5 | White King |

For each channel, `obs[channel][r][c] = 1.0` if a white piece of that type occupies square `(r, c)`, else `0.0`.

### Channels 6–11 — Black pieces

Same layout as 0–5, but for black pieces.

### Why separate channels per piece type?

The neural network needs to distinguish a pawn from a queen — they move completely differently. If you encoded all white pieces as just "1.0 = occupied by white", the network would have no way to know if the piece is a pawn or a queen. Separate binary channels make each piece type independently readable by the convolution/MLP.

---

### Channel 12 — Duck position

`obs[12][r][c] = 1.0` at the single square where the duck currently sits.  
All other squares in channel 12 are `0.0`.

The duck is not a piece — it has no color and cannot move like a chess piece. It gets its own dedicated channel so the network always knows exactly where the blocking obstacle is.

**What if the duck hasn't been placed yet?**  
On the very first half-move of the game (before any duck placement), `bb_mgr.duck_board == 0`. Channel 12 is all zeros. The network must handle this gracefully — and it does, because `0.0` in channel 12 is a valid input meaning "no duck yet".

---

### Channel 13 — En passant target

`obs[13][r][c] = 1.0` at the en passant target square (if any), else all zeros.

En passant is a special pawn capture rule: if a pawn just moved two squares, the opponent's pawn can capture it as if it had only moved one square, but only on the very next move.

The target square is the "ghost" square the moving pawn passed through. Encoding it as a channel lets the network know "a pawn can capture here this turn" without the network needing to infer it from move history.

---

### Channel 14 — Whose turn it is

The entire 8×8 channel is filled uniformly:
- `1.0` everywhere if it is White's turn
- `0.0` everywhere if it is Black's turn

**Why fill the whole channel instead of just one bit?**

The network processes each channel as a spatial feature map. A single bit buried at one corner would have very little influence on the network's activations. Broadcasting the same value across the full 8×8 plane gives the turn information equal "weight" alongside all the piece planes.

**Why does the network need to know whose turn it is?**

The observation is always from an absolute perspective (White pieces in channels 0–5, Black in 6–11). Without channel 14, the same board position looks identical regardless of whose turn it is — but the correct action is completely different. Channel 14 disambiguates: "it's White's turn, so channels 0–5 are the moving player".

---

### Channels 15–18 — Castling rights

| Channel | Castling right |
|---------|---------------|
| 15 | White can castle kingside (short) |
| 16 | White can castle queenside (long) |
| 17 | Black can castle kingside |
| 18 | Black can castle queenside |

Each channel is filled entirely with `1.0` if that right exists, `0.0` if it has been lost.

Castling rights are lost permanently when a king or rook moves. Encoding them lets the network understand whether castling is still available — a crucial strategic difference.

**Why 4 full channels for 4 bits?**

Same reason as channel 14 — uniform filling gives the network more signal per bit of information. Technically, four individual 0/1 scalars would suffice mathematically, but the MLP architecture processes spatial feature maps, not scalars.

---

### How the encoder is implemented — `observation_encoder.py`

```python
def encode_state(self, bb_mgr, turn, en_passant_target, can_castle_func):
    obs = np.zeros((19, 8, 8), dtype=np.float32)

    # Channels 0-11: iterate bitboards directly
    for color in ['w', 'b']:
        for p_type, channel in piece_to_channel.items():
            bb = bb_mgr.piece_boards[color][p_type[1]]
            for i in range(64):
                if bb & (1 << i):
                    obs[channel][i // 8][i % 8] = 1.0
```

The key design: the encoder reads from **bitboards**, not the 2D array. This is faster — iterating bits in a 64-bit integer only touches set bits (occupied squares), while iterating the 2D array always touches all 64 squares.

---

## The action space — 4096 integers

Every possible action — for both the piece phase and the duck phase — is encoded as a single integer in `[0, 4095]`.

### Encoding formula

```python
action_idx = (from_row * 8 + from_col) * 64 + (to_row * 8 + to_col)
```

This encodes a move as a pair of squares: **from** and **to**, each in range 0–63 (64 squares × 64 squares = 4096 combinations).

**Decoding:**
```python
start_sq = action_index // 64   # from-square
end_sq   = action_index % 64    # to-square
start = (start_sq // 8, start_sq % 8)
end   = (end_sq // 8,   end_sq % 8)
```

### The duck placement overload

Duck placement does not have a meaningful "from" square — the duck can go to any empty square regardless of where it was before. So duck moves are encoded with a **dummy from-square of (0, 0)**:

```python
# During move_duck phase:
action_idx = (0 * 8 + 0) * 64 + (to_row * 8 + to_col)
           = to_row * 8 + to_col   # effectively just the destination
```

This means action indices 0–63 are **overloaded**: they mean either  
- A piece move *from* square (0,0) = a8 (if `phase == 'move_piece'`)  
- A duck placement *to* some square (if `phase == 'move_duck'`)

**This is safe** because the engine phase disambiguates them. The `_apply_action` function in `env_base.py` asserts the invariant:

```python
if phase == 'move_piece':
    engine.execute_move(start, end, animated=False)
else:
    assert start == (0, 0)   # must be the dummy sentinel
    engine.place_duck(end, animated=False)
```

If these asserts ever fire, a bug has routed an action to the wrong phase.

### Why not a larger action space?

Alternative: use 64 actions for piece selection + 64 for destination = 128 actions (sequential). But that requires two sequential network queries per piece move (pick piece, then pick destination), which complicates the PPO rollout structure. A single 4096-dimensional action is simpler to train and lets the network express preferences over (from, to) pairs jointly.

### The action mask — `action_masker.py`

```python
masks = np.zeros(4096, dtype=bool)
```

**During `move_piece` phase:**

```python
my_pieces = bb_mgr.white_occupancy if turn == 'w' else bb_mgr.black_occupancy
for i in range(64):
    if my_pieces & (1 << i):          # for each of our pieces
        r, c = i // 8, i % 8
        for (dr, dc) in get_legal_moves(r, c):    # get all legal destinations
            masks[encode_move((r,c), (dr,dc))] = True
```

**During `move_duck` phase:**

```python
valid_duck_squares = ~bb_mgr.all_occupancy & 0xFFFFFFFFFFFFFFFF
# Also exclude the duck's current square (can't stay put):
valid_duck_squares &= ~(1 << (prev_duck_pos[0]*8 + prev_duck_pos[1]))

for i in range(64):
    if valid_duck_squares & (1 << i):
        masks[encode_move((0,0), (i//8, i%8))] = True
```

The duck mask uses `all_occupancy` (pieces + duck) to exclude occupied squares. Then it removes the duck's current square explicitly (`prev_duck_pos`) — the duck cannot stay in place.

---

## Summary: what the network actually processes

At each step, the network receives:

```
Input: float32[19, 8, 8] → flattened to float32[1224]
Mask:  bool[4096]        → passed to MaskablePPO
```

The network outputs:
```
Policy logits: float32[4096] → masked → softmax → action probabilities
Value:         float32[1]    → scalar estimate of position quality
```

The policy output directly indexes into the 4096-action space. After masking, sampling from this distribution always produces a legal move.
