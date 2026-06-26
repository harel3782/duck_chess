# Monte Carlo Tree Search (MCTS)

## File: `DuckChess_Game/SBThree/mcts.py`

MCTS is what makes the AI strong at inference time. The trained neural network alone (raw policy) makes decent moves but cannot "think ahead". MCTS adds look-ahead by building a search tree and using the neural network to guide and evaluate it.

---

## Why raw policy is not enough

After training, the policy network outputs a probability distribution over 4096 actions. It can choose "the move that looks best from this position" but it does not simulate what happens *after* that move.

**The value head problem:** The value head outputs V(s) — how good this position is. You might think: just pick the move that leads to the highest V(s'). This is called *greedy value selection* and it fails catastrophically in practice. The value head was trained as a byproduct of PPO, not as a standalone evaluator. It is noisy. Greedy selection amplifies its errors: every move choice is based on an imperfect evaluation, so the agent drifts toward positions the value head thinks are good but that are actually losing.

**Empirical result recorded in PLAN_V2.md:** greedy value selection dropped win rate vs Peter d2 from ~67% to 0%.

**The AlphaZero insight:** use the policy as a *prior* (which actions to explore first) and the value head only at *leaf nodes* (to estimate outcomes, not to select moves). The tree search aggregates many leaf evaluations, averaging out the noise. The most-visited action at the root — not the highest-value action — is what gets played.

---

## The PUCT formula

PUCT (Polynomial Upper Confidence Trees) is how MCTS decides which child to explore next:

```
score(a) = Q(a) + c_puct × P(a) × sqrt(N_total) / (1 + N(a))
```

Where:
- `Q(a)` = average value seen from action `a` so far = `W(a) / N(a)`  
  This is the **exploitation** term — prefer actions that have been good before
- `P(a)` = prior probability from the policy network  
  This is the **prior guidance** — prefer actions the policy thinks are good
- `N(a)` = visit count for action `a`  
  The denominator `1 + N(a)` shrinks the exploration bonus as `a` is visited more
- `sqrt(N_total)` = grows as more simulations run, increasing pressure to explore less-visited actions
- `c_puct = 1.5` = the exploration constant, balancing exploitation vs exploration

**Intuition:** Initially, all actions have `N(a) = 0`, so the formula is dominated by `P(a)` — the network's prior decides where to look first. As simulations accumulate, the `Q(a)` term takes over. Under-explored but promising actions get a boost from the growing `sqrt(N_total)` term.

---

## The two-level tree — handling the duck

Duck Chess has two-phase turns. The MCTS tree mirrors this:

```
Root node (phase=move_piece, White to move)
│
├── Action: move Pawn to e4        [piece node]
│     └── After duck placement → 
│           ├── Duck to d5         [duck node → new Root for Black]
│           ├── Duck to f6         [duck node → ...]
│           └── ...
│
├── Action: move Knight to f3      [piece node]
│     └── ...
└── ...
```

Each node stores:
- `engine` — a clone of the game state at that point
- `to_move` — which player is on turn
- `N[i]` — visit count for each kept action
- `W[i]` — total value accumulated for each kept action
- `P[i]` — prior probability for each kept action (from the policy network)
- `expanded` — whether this node has been evaluated yet

**Why two levels instead of one combined node?**

The policy network is called separately for piece moves and duck moves. If we collapsed piece+duck into a single "full turn" action, the action space would be 4096 × ~55 ≈ 225,000 combinations — computationally impossible to search. Keeping them as two tree levels means each node only fans out to ~8 or ~6 children (top-k by prior), giving a manageable branching factor.

**Sign flip rule:** Value propagation flips sign only when `child.to_move != node.to_move`. Between a piece node and its duck child, the player is the same — no flip. Between a duck node and its child (next player's piece node), the player changes — flip.

---

## The `_simulate` function — one MCTS rollout

```python
def _simulate(self, node: _Node) -> float:
    if node.terminal:
        return node.term_value       # game ended here
    if not node.expanded:
        return self._expand(node)    # first visit: evaluate the leaf
    
    # PUCT selection
    total_N = max(1.0, node.N.sum())
    q = np.where(node.N > 0, node.W / node.N, 0.0)
    u = self.c_puct * node.P * math.sqrt(total_N) / (1.0 + node.N)
    a_idx = int(np.argmax(q + u))
    action = node.actions[a_idx]
    
    # Expand child if not yet in tree
    child = node.children.get(action)
    if child is None:
        child = _Node(self._apply(node.engine, action))
        node.children[action] = child
    
    # Recurse and backup
    child_val = self._simulate(child)
    v = child_val if child.to_move == node.to_move else -child_val
    
    node.N[a_idx] += 1
    node.W[a_idx] += v
    return v
```

A single simulation: selection → expansion → backup. After 300 simulations (hard difficulty), `N` at the root reflects how many times each move was explored. The most-visited move is played — not the highest Q value.

---

## The `_expand` function — evaluating a leaf

When a node is visited for the first time:

```python
def _expand(self, node: _Node, add_noise: bool = False) -> float:
    node.expanded = True
    
    # Terminal check first
    if node.terminal:
        node.term_value = self._terminal_value(node.engine)
        return node.term_value
    
    masks = node.engine.action_masks()
    valid = np.where(masks)[0]
    
    if len(valid) == 0:
        # Fowling: the side to move has no legal moves → they WIN
        node.terminal = True
        node.term_value = 1.0
        return 1.0
    
    # Get full prior from the policy network
    priors_full = self._policy_probs(node.engine._get_obs(), masks)
    
    # Keep only top-k by prior
    topk = self.piece_topk if node.engine.phase == "move_piece" else self.duck_topk
    keep = [int(a) for a in np.argsort(-priors_full) if masks[a]][:topk]
    
    # Always force-include king captures with a boosted prior
    for a in valid:
        if self._captures_king(node.engine, int(a)) and int(a) not in keep:
            keep.append(int(a))
    
    # Set prior floor on king captures
    p = np.array([priors_full[a] for a in keep])
    for i, a in enumerate(keep):
        if self._captures_king(node.engine, a):
            p[i] = max(p[i], 1.0)    # force PUCT to explore it
    
    p /= p.sum()   # normalize
    
    node.actions = keep
    node.P = p
    node.N = np.zeros(len(keep))
    node.W = np.zeros(len(keep))
    
    return self._leaf_value(node.engine)    # V(s) from the value head
```

**Why prune to top-k?**

At a piece node, there might be 30+ legal moves. Exploring all 30 children 300 times would spread attention too thin. Limiting to the top 8 by policy prior focuses search on the most promising actions while keeping the tree manageable. King captures are always added regardless (they win the game).

**Dirichlet noise** (self-play only): when `add_noise=True`, root priors get mixed with random Dirichlet noise. This forces exploration of unusual openings, preventing self-play from collapsing to the same game every time.

---

## `_leaf_value` — querying the value head

```python
def _leaf_value(self, engine) -> float:
    with torch.no_grad():
        obs = torch.as_tensor(engine._get_obs()[None], device=self.model.policy.device)
        raw = self.model.policy.predict_values(obs).cpu().numpy().ravel()[0]
        return float(np.tanh(raw))
```

The value head outputs an unbounded scalar. `tanh` squashes it to (-1, 1), which aligns it with the ±1 terminal values used in backup. Without `tanh`, a large raw value at a leaf would dominate the backup and distort Q values everywhere.

`torch.no_grad()` prevents gradient computation — inference only, no training.

---

## `choose_turn` — the public API

```python
def choose_turn(self, engine) -> Tuple[Optional[int], Optional[int]]:
    assert engine.phase == "move_piece"
    
    # Forced king capture: check before any search
    masks0 = engine.action_masks()
    for a in np.where(masks0)[0]:
        if self._captures_king(engine, int(a)):
            return int(a), None    # instant win, no search needed
    
    root = _Node(clone_engine(engine))
    self._expand(root, add_noise=self.dirichlet > 0)
    
    for _ in range(self.sims):    # e.g., 300 simulations
        self._simulate(root)
    
    # Play the most-visited piece action
    piece_a = int(root.actions[int(np.argmax(root.N))])
    
    # Get the most-visited duck action under that piece move
    child = root.children.get(piece_a)
    duck_a = int(child.actions[int(np.argmax(child.N))])
    
    return piece_a, duck_a
```

The result is a `(piece_action, duck_action)` pair. The UI's `ai_turn()` in `turn_manager.py` calls this, then applies both actions in sequence.

---

## `headless_snapshot` — bridging UI and MCTS

The live Pygame game object (`DuckChess`) cannot be deepcopied — it holds Pygame surfaces. Before MCTS can search, it needs a clean, copyable version of the state:

```python
def headless_snapshot(game):
    e = _HeadlessEngine()
    e.board = copy.deepcopy(game.board)
    e.turn = game.turn
    e.phase = game.phase
    e.duck_pos = game.duck_pos
    e.prev_duck_pos = game.prev_duck_pos
    e.en_passant_target = game.en_passant_target
    e.half_move_clock = game.half_move_clock
    e.sync_bitboards_to_2d()    # rebuild bitboards from the 2D board
    return e
```

Called in `ai_turn()` before passing to `choose_turn()`. The 2D board (`game.board`) is deepcopy-safe because it is just Python lists and Piece objects — no Pygame. After copying, `sync_bitboards_to_2d()` rebuilds the bitboard representation from scratch.

---

## Performance numbers

| Parameter | Value | Why |
|-----------|-------|-----|
| `sims` | 300 (hard) / 100 (medium) / 30 (easy) | More simulations = stronger but slower |
| `c_puct` | 1.5 | Balances exploration; standard AlphaZero value |
| `piece_topk` | 8 | Keep 8 best piece moves per node |
| `duck_topk` | 6 | Keep 6 best duck placements per node |
| `dirichlet` | 0.3 (self-play), 0.0 (eval) | Exploration noise only during data generation |

At 300 simulations with topk=8 and topk=6, the tree can see approximately 8×6×8×6 = 2304 two-move sequences. In practice, the tree is skewed (popular moves are visited many times), so effective look-ahead is deeper than that.
