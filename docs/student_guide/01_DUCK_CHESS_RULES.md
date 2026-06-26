# Duck Chess Rules — and Where They Live in the Code

## Why this matters for the defense

Every design decision in the engine, the observation tensor, and the reward function traces back to the three special rules. If a committee member asks "why does your observation have 19 channels?" or "why is your endgame logic inverted?", the answer starts here.

---

## The three rules

### Rule 1 — The duck (two-phase turn)

After every normal chess move, the same player must **also move the neutral duck** to any empty square (it cannot stay put).  
The duck is indestructible. It blocks any square it sits on, for both sides.

**What this means for the engine:**  
Every turn has two sequential phases tracked by `engine.phase`:
- `"move_piece"` — a normal chess move
- `"move_duck"` — duck placement

`phase` lives directly on the engine object and is checked everywhere. The RL environment's `step()` only gives the agent its observation *once per phase*, so from the neural network's point of view it takes **two separate actions per full turn**: one piece action and one duck action.

**Where in the code:**  
- Phase transitions: [`turn_manager.py:79`](../../DuckChess_Game/Logic/turn_manager.py) — after executing a piece move, `self.phase = 'move_duck'`  
- Phase finalization: [`turn_manager.py:144`](../../DuckChess_Game/Logic/turn_manager.py) — after placing the duck, `self.phase = 'move_piece'` and `self.turn` flips  
- Duck on the board: channel 12 of the observation tensor  
- Duck blocking: the action masker uses `bb_mgr.all_occupancy` (which includes the duck) to exclude occupied squares from legal destinations

---

### Rule 2 — Win by king capture

There is **no check, no checkmate**. You win by *physically capturing the enemy king* on your move.

**Why this is a big deal:**  
In standard chess, the engine never needs to allow a king capture — it is implicitly forbidden. Here, king captures are the *only* win condition and must be explicitly detected and terminated mid-move.

**Where in the code:**  
[`turn_manager.py:63`](../../DuckChess_Game/Logic/turn_manager.py):

```python
if captured and captured.type == KING:
    self.game_over, self.winner = True, self.turn
```

This runs inside `execute_move()`, immediately after `MoveExecutor` applies the piece move. If the captured piece is a king, the game ends right there — the duck phase never happens. `self.winner` is set to whoever just moved (`self.turn` before the flip).

**MCTS special case:**  
Because the policy neural network often assigns very low probability to king captures (it sees them rarely in training), MCTS would never explore them. This is corrected in [`mcts.py:109-115`](../../DuckChess_Game/SBThree/mcts.py):

```python
for a in np.where(masks0)[0]:
    if self._captures_king(engine, int(a)):
        return int(a), None   # skip the search entirely, play the winning move
```

This short-circuit runs before any MCTS simulations. It also re-runs inside `_expand()` to guarantee any king capture kept in the top-k has a non-zero prior floor:

```python
for i, a in enumerate(keep):
    if self._captures_king(node.engine, a):
        p[i] = max(p[i], 1.0)   # force PUCT to explore it
```

---

### Rule 3 — Fowling (no legal moves = you WIN)

In standard chess, having no legal moves is stalemate — a draw, and often a resource for the losing side. In Duck Chess, it is the **opposite**: if it is your turn and you have no legal piece moves, **you win**.

This rule is called *Fowling* (the duck traps you like a fowler traps birds).

**Why it is inverted:**  
The duck can be used to block your own pieces on purpose, for strategic reasons — or to trap the opponent so they can't move and you win. This creates a completely different endgame dynamic.

**Where in the code:**  
[`endgame_checker.py:37`](../../DuckChess_Game/Logic/endgame_checker.py):

```python
if not has_moves:
    self.game_over = True
    self.winner = self.turn   # the player with no moves WINS
```

And in MCTS `_expand()` ([`mcts.py:238`](../../DuckChess_Game/SBThree/mcts.py)):

```python
if len(valid) == 0:
    node.terminal = True
    node.term_value = 1.0   # fowling: side to move wins
    return 1.0
```

**Training impact:**  
The reward calculator must correctly assign `+1.0` to fowling wins. `TerminalReward.calculate()` does this by checking `engine.winner == learning_color` — which is correct whether the win came from king capture or fowling, because both set the same `game_over`/`winner` fields.

---

### Rule 4 — The only draw: 50-move rule

The 50-move rule works like standard chess: if 50 full moves pass with no pawn move or capture, the game is a draw. Internally this is tracked as 100 half-moves (`half_move_clock`).

There is **no** draw by repetition, no draw by insufficient material. Any position can theoretically be won.

**Where in the code:**  
[`endgame_checker.py:22`](../../DuckChess_Game/Logic/endgame_checker.py):

```python
if self.half_move_clock >= 100:
    self.game_over, self.winner = True, 'draw'
```

`half_move_clock` is reset to 0 on any pawn move or capture ([`turn_manager.py:44-47`](../../DuckChess_Game/Logic/turn_manager.py)):

```python
if p.type == PAWN or is_capture:
    self.half_move_clock = 0
else:
    self.half_move_clock += 1
```

---

## Common mistakes / traps for the defense

| Wrong assumption | Correct fact |
|-----------------|--------------|
| "Stalemate is a draw" | No — no legal moves is a *win* (Fowling) |
| "You win by putting the king in check" | No — you win by *capturing* the king |
| "The duck is one player's piece" | No — it is neutral, it blocks both sides |
| "A turn is one action" | No — every turn is two actions: piece move then duck placement |
| "Draws happen often (repetition, etc.)" | Only the 50-move rule draws. Everything else resolves. |
