# Duck Chess AI — Student Guide Index

This folder contains deep-dive documentation written for CS students preparing to present or defend this project. Each file explains not just *what* the code does but *why* it was built that way.

**Read in order if you are new to the project.  
Jump to a specific file if you need to brush up on one area.**

---

## Files in this guide

| File | What it covers |
|------|---------------|
| [01_DUCK_CHESS_RULES.md](01_DUCK_CHESS_RULES.md) | The three special rules, how they differ from chess, and exactly where each is enforced in the code |
| [02_GAME_ENGINE.md](02_GAME_ENGINE.md) | Dual board representation (2D array + bitboards), mixin architecture, move generation, the two-phase turn |
| [03_RL_FOUNDATIONS.md](03_RL_FOUNDATIONS.md) | Reinforcement learning basics, why PPO, what MaskablePPO adds, how the training loop works |
| [04_OBSERVATION_AND_ACTIONS.md](04_OBSERVATION_AND_ACTIONS.md) | The 19×8×8 observation tensor and 4096 action space — every channel explained with design rationale |
| [05_TRAINING_ENVIRONMENT.md](05_TRAINING_ENVIRONMENT.md) | BaseDuckChessEnv, the step loop, reward calculators (sparse vs shaped), curriculum stages |
| [06_MCTS.md](06_MCTS.md) | AlphaZero-style PUCT Monte Carlo Tree Search — the math, the two-level tree, why it beats raw policy |
| [07_EXPERT_ITERATION.md](07_EXPERT_ITERATION.md) | Expert Iteration end-to-end: generate → train → eval → advance, data format, training losses |
| [08_MODELS_AND_RESULTS.md](08_MODELS_AND_RESULTS.md) | All five ranked models, how they were produced, evaluation methodology, the depth-3 wall |

---

## Quick orientation — how the three parts connect

```
┌─────────────────────────────┐
│       Game Engine           │  Pure Python. No ML.
│  Logic/ (logic.py + mixins) │  Enforces rules, generates moves,
│                             │  exposes _get_obs() and action_masks()
└──────────────┬──────────────┘
               │  _HeadlessEngine wraps it for training
               ▼
┌─────────────────────────────┐
│     RL Environment          │  Gymnasium-compatible.
│  SBThree/base/env_base.py   │  Feeds observations to the policy,
│                             │  applies actions, computes rewards.
└──────────────┬──────────────┘
               │  SubprocVecEnv parallelises many copies
               ▼
┌─────────────────────────────┐
│     MaskablePPO             │  sb3-contrib. Trains the neural net.
│     (policy + value head)   │  Policy → which move to play.
│                             │  Value  → how good is this position.
└──────────────┬──────────────┘
               │  At inference: policy+value feed into MCTS
               ▼
┌─────────────────────────────┐
│     DuckMCTS (mcts.py)      │  AlphaZero-style look-ahead.
│     Expert Iteration loop   │  MCTS data → retrain both heads →
│  (run_exit / train_exit)    │  repeat. The champion model lives here.
└─────────────────────────────┘
```

---

## Key numbers to remember for the defense

| Thing | Value |
|-------|-------|
| Observation shape | 19 × 8 × 8 |
| Action space size | 4096 |
| Piece channels | 0–5 (white), 6–11 (black) |
| Duck channel | 12 |
| Turn channel | 14 |
| Castling channels | 15–18 |
| MCTS simulations (hard difficulty) | 300 |
| Top-k piece moves explored by MCTS | 8 |
| Top-k duck moves explored by MCTS | 6 |
| Champion model score vs Peter d1 | 1.00 (20/0/0) |
| Champion model score vs Peter d2 | 1.00 (20/0/0) |
| Champion model score vs Peter d3 | 0.00 — open challenge |
