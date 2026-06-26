# Reinforcement Learning Foundations

## What problem RL is solving here

We want to train a neural network to play Duck Chess well. The challenge: there is no labeled dataset of "good moves" — chess databases are not valid (different rules) and human Duck Chess games are scarce. Instead, we let the agent **learn by playing**, receiving a reward signal only when the game ends.

This is the Reinforcement Learning paradigm: an **agent** observes a **state**, picks an **action**, receives a **reward**, and transitions to the next state. Over many episodes it learns which actions lead to more reward.

---

## Markov Decision Process (MDP) — the formal framing

The game is modeled as a discrete-time MDP:

| MDP term | Duck Chess equivalent |
|----------|-----------------------|
| State *s* | The board position encoded as a 19×8×8 float tensor |
| Action *a* | An integer in [0, 4095] representing a move |
| Reward *r* | +1.0 win, −1.0 loss, 0.0 otherwise (sparse terminal) |
| Transition *T(s,a)* | Deterministic: the engine's `execute_move` / `place_duck` |
| Episode termination | King captured, Fowling, or 50-move draw |

The agent's goal is to find a **policy** π(a|s) — a probability distribution over actions given the state — that maximises the **expected discounted return**: sum of future rewards weighted by γ^t.

---

## Why PPO?

**Proximal Policy Optimization** is the chosen algorithm. It belongs to the *policy gradient* family: instead of learning a value table (which doesn't scale to 4096 actions × huge state space), it directly parameterises the policy as a neural network and optimises it with gradient ascent.

PPO's defining feature is the **clipped surrogate objective**:

```
L_CLIP = E[ min( r_t(θ) * A_t,  clip(r_t(θ), 1-ε, 1+ε) * A_t ) ]
```

Where:
- `r_t(θ) = π_θ(a|s) / π_old(a|s)` — the ratio of new policy to old policy  
- `A_t` — the **advantage**: how much better this action was than average  
- `ε` ≈ 0.2 — the clip range

**Why the clip?** Without it, a large gradient update could make the policy change so drastically that it collapses (the infamous "catastrophic forgetting" in policy gradient). The clip prevents any single update from moving the policy ratio outside [0.8, 1.2], keeping training stable.

**Why not DQN / Q-learning?** DQN learns Q(s,a) values for every action. With 4096 possible actions and a continuous, high-dimensional state space, Q-learning is notoriously unstable and slow. Policy gradient methods handle large action spaces more naturally.

---

## Why `sb3-contrib` MaskablePPO?

Standard PPO samples actions from the full action distribution, including illegal moves. In most RL domains (Atari, MuJoCo) every action is at least *technically* legal. In chess, roughly 4000 of 4096 actions are illegal at any given position.

If the agent samples an illegal action:
- The environment would have to handle it somehow (ignore, penalize, or crash)
- Training signal becomes noisy — the policy learns "penalized for X" rather than "X was strategically bad"
- The policy wastes probability mass on moves it can never play

**MaskablePPO** zeroes out logits for illegal actions before the softmax, so the sampled distribution only covers legal moves. This is not an approximation — it is the correct formulation:

```python
# Inside MaskablePPO's forward pass (simplified):
logits = self.action_net(latent_pi)          # raw scores for all 4096 actions
logits[~mask] = -inf                         # illegal actions → -∞
probs = softmax(logits)                      # now sums to 1.0 over legal moves only
action = Categorical(probs).sample()
```

This is enforced via the `action_masks()` method on the environment:

```python
def action_masks(self) -> np.ndarray:
    return self._mask.get_masks(self.engine)   # bool[4096]
```

`MaskablePPO` calls `action_masks()` automatically at every step during training.

**This is a correctness invariant, not an optimization.** If illegal actions are ever allowed through, the agent could select a "move" that puts two pieces on the same square or moves a pawn backwards — the engine would reject it, training signal would be corrupted, and the policy would never converge.

---

## The neural network architecture

MaskablePPO uses a shared `MlpPolicy` (multi-layer perceptron):

```
Input: 19×8×8 tensor
  → FlattenExtractor  →  1224-dim vector   (19 × 8 × 8 = 1224)
  → Shared MLP
      ┌──────────────────────────┐
      │  features_extractor(x)   │   (just the flatten; no CNN)
      └────────┬─────────────────┘
               ├──────────────────────────────────┐
               ▼                                  ▼
      mlp_extractor.forward_actor         mlp_extractor.forward_critic
         (policy_net)                        (value_net)
               │                                  │
               ▼                                  ▼
         action_net                           value_net
       → 4096 logits                       → 1 scalar V(s)
```

**Why no CNN?** A CNN would be the natural choice for a 2D board (like AlphaZero uses). Here, a flat MLP was chosen to keep training fast on CPU and to avoid having to design convolutional kernels that handle the 19-channel duck-chess-specific input. The MLP is simpler and still strong enough when guided by MCTS.

**Two heads:**
- **Policy head** (`action_net`): outputs 4096 logits → after masking and softmax → move probabilities
- **Value head** (`value_net`): outputs a scalar → how good is this position for the current player

Both heads are trained simultaneously by PPO (policy loss + value loss weighted by `vf_coef`).

---

## The training loop (high level)

```
repeat many times:
  1. Run N episodes in parallel (SubprocVecEnv), collect (s, a, r, s', done)
  2. Compute advantages: A_t = r_t + γ*V(s_{t+1}) - V(s_t)   [GAE variant]
  3. Update policy: gradient ascent on L_CLIP using the collected rollouts
  4. Update value head: minimize MSE( V(s_t) - (r_t + γ*V(s_{t+1})) )
  5. Optionally save a checkpoint, evaluate vs Peter
```

**SubprocVecEnv** runs multiple game environments in separate processes simultaneously. This is critical for throughput — one game at a time would be 4× slower than 4 parallel games.

---

## Sparse vs dense reward — a crucial choice

The production training uses **sparse terminal reward only**:
- `+1.0` when the agent wins
- `-1.0` when the agent loses
- `0.0` at every intermediate step

**Why not give intermediate rewards** (e.g., +0.1 for capturing a queen)?

Dense rewards *guide* the agent but also *mislead* it. If you reward capturing pieces, the agent learns to chase captures even when strategically wrong (sacrificing a queen to capture a pawn, then losing the king). In Duck Chess especially, the duck mechanic means positional value is highly non-standard.

Sparse reward forces the agent to discover strategy on its own from the outcome signal, which generalizes better — the `1_champion.zip` model was trained with sparse reward and Expert Iteration.

Earlier training stages used the `ShapedReward` (dense) calculator as a bootstrap — to give the agent *any* learning signal before it understood the game well enough to win or lose deliberately. See [`05_TRAINING_ENVIRONMENT.md`](05_TRAINING_ENVIRONMENT.md) for details.

---

## How `gamma` (discount factor) works with sparse reward

With `γ < 1.0`, rewards far in the future are worth less. With sparse reward (reward only at game end), this means the agent prefers *shorter* winning paths — which is the correct behavior. A win in 10 moves is better than a win in 100 moves.

With `γ = 1.0` and sparse reward, all winning paths are equally valued regardless of length — which can lead to passive play and slow-win strategies that are harder to train.

PPO typically uses `γ ≈ 0.99`.
