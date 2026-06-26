# Expert Iteration (ExIt)

## Files covered

```
DuckChess_Game/SBThree/
  run_exit.py        ← orchestrator loop
  gen_mcts_data.py   ← step 1: generate MCTS self-play data
  train_exit.py      ← step 2: train both heads on MCTS targets
  eval_search.py     ← step 3: evaluate with MCTS vs Peter
```

---

## Why Expert Iteration and not just more PPO?

After many training stages, PPO with sparse reward hit a ceiling. The model learned to beat Peter d1 and d2 but could not break through to d3.

**The diagnosis:** PPO learns from the model's own experience. If the model plays poorly in some situation, it gets a losing outcome and adjusts — but it might take thousands of games to encounter and correct that specific situation. PPO cannot "look ahead" — it just records what happened and what the outcome was.

**The Expert Iteration idea** (Schmitt et al. 2018, also the core of AlphaZero): instead of learning from your own moves, learn from the moves that *MCTS* would choose. MCTS is a better player than the raw policy — it thinks ahead. If we:

1. Run MCTS to play games, recording what it chose at each position
2. Train the network to imitate those choices

...then the network improves by learning from a *stronger teacher* than itself. When we repeat this cycle, each iteration's network is better than the last, and so the MCTS teacher also becomes stronger.

---

## The ExIt loop — `run_exit.py`

```
current_model = base_model   (the strong PPO model)

for each iteration:
    1. GENERATE  — run MCTS games → save (obs, π, z) dataset
    2. TRAIN     — warm-start from current_model, regress both heads onto (π, z)
    3. EVALUATE  — test new model with MCTS vs Peter d1, d2, d3
    4. ADVANCE   — current_model = new_model  (always accept)
                   if new_model is best so far → save as exit_best.zip
```

**Always-accept** (AlphaZero-style): unlike league-based training where you might reject a worse model, ExIt always advances. The rationale: even a slightly regressed model produces better training data than a strong-but-stale one, because it generates new positions and new tree searches.

**Guard the best:** A separate `exit_best.zip` is kept as a safety net. It is updated whenever `(d1_score + d2_score, d3_score)` improves. If a late iteration regresses badly, the best model is not lost.

---

## Step 1 — Generate MCTS data (`gen_mcts_data.py`)

### What gets recorded

For each position visited during an MCTS game:

```python
(obs, pi_idx, pi_val, z)
```

- `obs` — the 19×8×8 observation at that position
- `pi_idx` — the action indices that MCTS visited (top-k, padded with -1)
- `pi_val` — the visit-count distribution, normalized to sum to 1.0
- `z` — the game outcome from that position's side: +1.0 if that side won, -1.0 if lost, 0.0 draw

### The π target — why visit counts, not Q values

The MCTS visit-count distribution `π` is the *improved policy*. An action visited 200 times out of 300 total simulations means MCTS thinks it is the best move about 67% of the time after thinking hard. This is a richer training signal than just "the move I played" — it carries information about the *confidence* of the search.

Training the policy to match π is better than behavioral cloning (just copy the greedy best move), because:
- π is a distribution, not a point — it provides gradient signal for all explored actions
- π reflects the search's uncertainty, which regularizes against overconfidence

### The duck node — recording both phases

```python
targets = []
# Record the piece-move node
piece_pi = root.N / root.N.sum()
targets.append((root.engine._get_obs(), list(root.actions), piece_pi, root.to_move))

# Record the duck-placement node
duck_pi = child.N / child.N.sum()
targets.append((child.engine._get_obs(), list(child.actions), duck_pi, child.to_move))
```

Both the piece-move and duck-placement nodes generate training targets. This is essential — without duck node targets, the policy never gets direct supervision on *where to place the duck*. The duck placement was one of the identified behavioral exploits (random-looking duck moves) and recording duck targets directly addresses it.

### Mixed opponent strategy

```python
self_games  = games * (1 - peter_frac)   # e.g., 60% self-play
peter_games = games * peter_frac          # e.g., 40% vs Peter
```

**Self-play** (Dirichlet noise on, temperature=1.0 for first 12 turns):
- Generates diverse positions across the whole game
- Temperature sampling means different games explore different openings

**vs Peter** (no Dirichlet noise, mix of d1 and d2):
- d1 = Peter depth-1, plays aggressive king-rush moves. Trains defense against human-style attacks.
- d2 = Peter depth-2, plays proper positional moves. Trains strategic play.

Why not d3? d3 is the target wall, not the training opponent — you do not train by playing someone you cannot beat yet.

### Parallelization

```python
ctx = mp.get_context("spawn")
with ctx.Pool(len(payloads)) as pool:
    results = pool.map(_worker, payloads)
```

Each worker process loads the model independently and generates its fraction of games in parallel. `spawn` context is required on Windows (the default `fork` context does not work with PyTorch models on Windows).

---

## Step 2 — Train both heads (`train_exit.py`)

### The two losses

```python
def heads(obs_t):
    feats = policy.extract_features(obs_t)
    latent_pi = policy.mlp_extractor.forward_actor(feats)
    latent_vf = policy.mlp_extractor.forward_critic(feats)
    logits = policy.action_net(latent_pi)
    value = torch.tanh(policy.value_net(latent_vf).squeeze(-1))
    return logits, value

# Policy loss: cross-entropy with MCTS visit distribution
tgt = _target_dist(pi_idx, pi_val, dev)   # dense (B, 4096) target
logp = F.log_softmax(logits, dim=1)
ploss = -(tgt * logp).sum(1).mean()       # CE = -sum(π * log(p))

# Value loss: MSE between tanh(value) and game outcome z
vloss = F.mse_loss(value, z_batch)

loss = ploss + vf_coef * vloss            # vf_coef=1.0 gives equal weight
```

**Policy loss — cross-entropy with π:**

Standard cross-entropy between the network's log-softmax and the MCTS visit distribution. This is exactly the AlphaZero policy head loss. The target `tgt` is a dense (B, 4096) matrix where most entries are 0, but the top-k visited actions have the visit probabilities. The `_target_dist` function scatters the sparse `(pi_idx, pi_val)` into this dense format using `scatter_add_`.

Note: the CE is computed over all 4096 logits with `log_softmax`, *without* applying the legal-move mask. This is the standard AlphaZero arrangement — the mask is only applied at inference (in `mcts.py` and `eval_search.py`). Training without a mask lets the network learn that illegal moves should have low probability naturally.

**Value loss — MSE with z:**

`tanh(value_head_output)` compared against `z ∈ {-1, 0, 1}`. The `tanh` squash ensures the predicted value stays in (-1, 1), matching the range of z. MSE penalizes the value head for being wrong about who wins.

### Warm-starting

```python
model = MaskablePPO.load(base, device="cpu")
policy = model.policy
for prm in policy.parameters():
    prm.requires_grad_(True)
opt = torch.optim.Adam(..., lr=lr)    # lr = 1e-4
```

The model is loaded from the previous iteration's checkpoint. All parameters are unfrozen and trained with Adam at a low learning rate (1e-4). The low learning rate is critical: aggressive updates on a small batch of MCTS data could overwrite the strong general policy learned over many millions of PPO steps.

Gradient clipping (`max_grad_norm=0.5`) prevents runaway updates when the loss gradient is unusually large.

### The replay window

```python
data_window.extend(files_this)
data_window = data_window[-window:]   # keep last `window` iterations of data
train_exit(current, data_window, ...)
```

Training on the last 4 iterations' data (default `window=4`) instead of just the most recent:
- More data → more stable gradient estimates
- Older data prevents the network from "forgetting" positions from earlier iterations
- Without a window, training on too-fresh data can cause instability (the data distribution shifts every iteration)

---

## Step 3 — Evaluate (`eval_search.py`)

After each training step, the new model is tested with MCTS against Peter at three depths:

- **d1** (depth-1): Peter plays aggressive king-rush. Represents human attack style.
- **d2** (depth-2): Peter plays proper positional play. Represents strong classical play.
- **d3** (depth-3): Peter plays deep tactical play. The unsolved wall.

Score formula: `(wins + 0.5 × draws) / total_games`

---

## Step 4 — Advance and guard best

```python
current = model_it    # always accept the new model

key = (round(r1["score"] + r2["score"], 3), r3["score"])
if key > best_key:
    best_key = key
    shutil.copyfile(model_it, best_path)    # save exit_best.zip
```

The *key* prioritizes `d1 + d2` (human-relevant robustness) and tiebreaks with `d3`. A model that beats both human-style (d1) and positional (d2) play is more practically useful than one that only does well on d3 (which is 0% for every model anyway).

---

## Data format — the `.npz` file

```python
np.savez_compressed(out,
    obs    = float32[N, 19, 8, 8],   # board observations
    pi_idx = int32[N, K],            # action indices with MCTS visits (K=16 max)
    pi_val = float32[N, K],          # visit probabilities (rows sum to 1)
    z      = float32[N],             # outcomes in {-1, 0, +1}
)
```

`N` = total number of half-move positions recorded (both piece-phase and duck-phase nodes from all games). With 500 games and ~50 moves per game and ~2 targets per turn = ~50,000 positions per iteration file.

`K = 16` — the maximum number of visited actions stored per position. If MCTS visited more than 16 unique actions, only the top 16 by visit mass are kept. Actions beyond 16 receive negligible visit counts and contribute almost nothing to the CE loss.

---

## The three exploits ExIt was designed to fix

Before ExIt, profiling revealed three systematic weaknesses:

1. **Opening repetition** — the raw policy always played the same opening moves, making it predictable and exploitable. ExIt's temperature sampling + Dirichlet noise at generation time forces diverse openings into the training data.

2. **Weak duck placement** — the policy placed ducks near-randomly. By recording and training on duck-phase MCTS targets specifically, ExIt gives the duck placement direct supervision from a stronger teacher.

3. **Endgame collapse** — the model often failed to convert won positions. Training against Peter d1 (which plays aggressively) provided endgame conversion examples in the generated data.

The result: `1_champion.zip` (ExIt iteration 1) scores 1.00 vs Peter d1 and 1.00 vs Peter d2 — perfect scores that no previous model achieved at both depths simultaneously.
