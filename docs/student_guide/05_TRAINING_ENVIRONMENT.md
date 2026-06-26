# Training Environment

## File: `DuckChess_Game/SBThree/base/env_base.py`

The training environment is the "game wrapper" that MaskablePPO trains inside. It implements the Gymnasium `gym.Env` interface so it can plug into any standard RL library.

---

## The three strategy objects — dependency injection

`BaseDuckChessEnv` does not hard-code any behavior. Instead, everything variable is passed in via an `EnvConfig` dataclass:

```python
@dataclass
class EnvConfig:
    stage_name:   str
    opponent:     OpponentStrategy    # who plays the other side
    reward:       RewardCalculator    # how reward is computed
    mask:         MaskStrategy        # which actions are legal
    randomize_color: bool = True      # agent plays random color each episode
    max_episode_plies: int = 0        # soft move limit (0 = disabled)
```

This is the **Strategy pattern** from software design. The same `BaseDuckChessEnv` class produces radically different training environments just by swapping these three objects:

- Give it `PeterLocalOpponent` and you train against the Peter engine
- Give it `SelfPlayOpponent` and you train against yourself
- Give it `ShapedReward` instead of `TerminalReward` and you get dense intermediate feedback

---

## The Gymnasium interface

Gymnasium (formerly OpenAI Gym) defines three mandatory methods:

### `reset(seed, options) → (obs, info)`

Called at the start of each episode. In `env_base.py:111`:

1. Reset the `_HeadlessEngine` to the starting position
2. Randomly choose whether the agent plays White or Black (when `randomize_color=True`)
3. If the agent plays Black, run `_play_opponent_turn()` so it's immediately the agent's turn
4. Return the initial observation

**Why randomize color?**  
Chess has a first-move advantage. If the agent always played White, it would learn White's opening theory but have no idea how to defend against it as Black. Randomizing color forces the network to learn symmetric play.

### `step(action) → (obs, reward, terminated, truncated, info)`

The core of the training loop. Called once per action the agent takes. In `env_base.py:131`:

```python
def step(self, action: int):
    # 1. Capture pre-state for reward calculation
    pre = self._reward.capture_pre_state(self.engine, action, self.learning_color)
    
    # 2. Apply the agent's action
    self._apply_action(action)
    self._ply_count += 1
    
    # 3. Capture post-state
    post = self._reward.capture_post_state(self.engine, self.learning_color)
    
    # 4. Check if the game ended after the agent's action
    terminated = self.engine.game_over
    
    # 5. If NOT terminated and the agent's full turn is done (phase flipped back
    #    to move_piece), let the opponent play their full turn
    if not terminated and self.engine.phase == 'move_piece':
        self._play_opponent_turn()
        terminated = self.engine.game_over
    
    # 6. Compute reward
    reward = self._reward.calculate(pre, post, self.engine, self.learning_color, terminated)
    
    return self.engine._get_obs(), reward, terminated, False, {}
```

**Key detail:** `step()` is called once for the piece action and once for the duck action. After the duck action, `self.engine.phase` flips back to `'move_piece'` — that is the signal that the agent's full turn is complete and the opponent should now play.

### `action_masks() → bool[4096]`

Called by MaskablePPO before every `step()` to know which actions are legal. Delegates to `MaskStrategy.get_masks(engine)`.

---

## `_apply_action(action)` — the phase-safe dispatcher

```python
def _apply_action(self, action: int) -> None:
    start, end = self.engine._decode_move(action)
    phase = self.engine.phase
    assert phase in ('move_piece', 'move_duck')
    if phase == 'move_piece':
        self.engine.execute_move(start, end, animated=False)
    else:
        assert start == (0, 0)   # duck sentinel
        self.engine.place_duck(end, animated=False)
```

The two asserts are the safety net for the 4096-space overloading issue: if a duck action is somehow dispatched during `move_piece` phase (or vice versa), the assert fires immediately with a clear message instead of silently corrupting the board state.

---

## `_play_opponent_turn()` — the opponent loop

```python
def _play_opponent_turn(self) -> None:
    while (
        self.engine.turn == self.opponent_color
        and not self.engine.game_over
    ):
        opp_masks = self._mask.get_masks(self.engine)
        if not np.any(opp_masks):
            # Fowling: opponent has no legal moves → they win
            self.engine.game_over = True
            self.engine.winner = 'draw'   # treated as draw from training perspective
            break
        opp_action = self._opponent.get_action(self.engine, opp_masks)
        self._apply_action(opp_action)
```

The `while` loop (not `if`) handles the two-phase turn: the opponent must play both their piece move AND their duck placement before control returns to the agent. Each call to `_apply_action` advances the phase; after the duck is placed, `engine.turn` flips back to the agent's color and the loop exits.

---

## Reward Calculators

### `TerminalReward` — sparse (production)

```python
def calculate(self, pre, post, engine, learning_color, terminated):
    if not terminated:
        return 0.0                    # no signal during the game
    winner = engine.winner
    if winner == learning_color:
        return self.win    # default +1.0
    if winner in ('draw', None):
        return self.draw   # default  0.0
    return self.loss       # default -1.0
```

Simple. Clean. The agent must figure out strategy entirely from the win/loss outcome.

**Problem:** In the early stages of training, the agent plays random moves and rarely wins or loses in an interesting way. The reward signal is so sparse that learning is extremely slow.

### `ShapedReward` — dense (bootstrap/curriculum stages)

Used in earlier training stages to give the agent a head start:

**Material reward:**
```python
diff = (material_post - material_pre) * sign
reward += diff * self.material_weight   # e.g., +0.05 for capturing a pawn
```

**Duck placement reward:**
```python
# How many opponent moves did our duck just remove?
removed = opp_mob_before - opp_mob_after
reward += min(removed, cap) * self.duck_placement_bonus
```

This teaches the agent to place the duck strategically — next to the opponent's king, blocking escape routes.

**King push reward** (endgame):
```python
if material_advantage > threshold:
    dist_before = center_distance(opp_king_pos)
    dist_after  = center_distance(opp_king_new_pos)
    if dist_after > dist_before:
        reward += delta * self.king_push_bonus
```

Encourages pushing the opponent's king to the edge when ahead in material — a classic endgame technique.

**The shaped reward dilemma:**  
Dense rewards help early in training but hurt late. An agent optimized for material capture might sacrifice its king to get a pawn. The solution used here was: start with shaped reward to bootstrap basic piece play, then switch to sparse terminal reward for the final training stages.

---

## Curriculum — the stage progression

The project trained through ~14 stages, each with a different environment config:

| Stage range | Opponent | Reward | Goal |
|-------------|---------|--------|------|
| Stages 1–3 | Random legal moves | Sparse | Learn valid piece movement |
| Stages 4–10 | Previous model checkpoint (league self-play) | Shaped | Learn tactics and material |
| Stages 11–13 | Peter depth-1/2 + league | Sparse | Learn to beat a real engine |
| Stage 14 recovery | Peter + historical checkpoints | Sparse | Recover from regression |
| antiexploit_v2 | Peter + corrective data | Sparse | Fix specific behavioral exploits |
| ExIt | MCTS self-play + Peter d1/d2 | MCTS targets (π, z) | Distil search into the network |

**The league self-play loop** (stages 10+): a `LeagueCallback` periodically saves the current model as a checkpoint and adds it to a pool of historical opponents. The agent trains against a random mix of recent and old versions, preventing it from finding "quirks" that only beat itself.

---

## `_HeadlessEngine` — why it exists

```python
class _HeadlessEngine(GameLogicMixin):
    def __init__(self):
        self.game_mode = 'rl_training'
        self.reset_game_state()
```

This is the engine used for all RL training. It is identical to the `DuckChess` game used in the UI, except:

- No Pygame import → can run on a server with no display
- `game_mode = 'rl_training'` → skips sound, skips replay recording, auto-queens all promotions
- Can be `deepcopy`-ed safely → allows MCTS to fork engine states for tree search

The `deepcopy` point is critical. The UI's `DuckChess` class contains Pygame `Surface` objects that cannot be pickled or copied. `_HeadlessEngine` has none of those, so `clone_engine()` in `search.py` can create a branch for every MCTS node without crashing.
