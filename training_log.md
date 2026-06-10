# Duck Chess AI — Training Log

A stage-by-stage record of the reinforcement-learning curriculum. The headline lesson runs through
the whole log: **self-play strength is not real strength.** Models that dominated internally
collapsed against the alpha-beta **Peter** engine, so later stages train and measure against Peter
directly (`eval_vs_peter.py` is the source of truth).

Reward convention: **sparse terminal** = +1 win / −1 loss / +0.1 draw, 0 otherwise. **Dense** =
per-move shaping (development, king safety, material, mobility, duck-blocking).

---

## Stage 1 — Random Bot ("Kindergarten")
- **Date:** 2026-03-15
- **Goal:** Learn basic legal moves and how to capture the king.
- **Opponent:** Random.
- **Steps:** 100,000.
- **Reward:** Dense.
- **Result:** `ep_rew_mean` ≈ 0.9. Completed.
- **Checkpoint / env:** `duck_stage1_final.zip` · `duck_env_stage1_random.py`

## Stage 2 — Greedy Bot ("Elementary")
- **Date:** 2026-03-27
- **Goal:** Defend pieces and handle aggressive captures.
- **Opponent:** Greedy bot (always takes any available capture).
- **Steps:** 500,000.
- **Result:** Learned basic material preservation against immediate threats.
- **Checkpoint:** `duck_stage2_greedy.zip`

## Stages 3–8 — Dense Reward & Mechanics ("Middle School")
- **Date:** 2026-04-01 → 2026-04-14
- **Goal:** Move to the bitboard architecture, optimize legal-move masking, stabilize early
  self-play.
- **Opponent:** Fixed previous versions.
- **Steps:** ~5,000,000 combined.
- **Reward:** Dense (material captures).
- **Result:** Gymnasium environment logic validated; reward function stabilized.

## Stage 9 — Self-Play Baseline ("League Intro")
- **Date:** 2026-04-15 → 2026-04-19
- **Goal:** Establish a strong self-play baseline before dynamic-pool generation.
- **Opponent:** Latest self-play clones, continuously updating.
- **Steps:** 3,000,000.
- **Checkpoint:** `stage9_selfplay_latest.zip`

## Stage 10 — League Play ("High School")
- **Date:** 2026-04-20 → 2026-04-26
- **Goal:** High mobility, endgame play, and resistance to catastrophic forgetting.
- **Opponent:** Dynamic league (random historical snapshots vs latest).
- **Steps:** 4,000,000.
- **Architecture:** `SubprocVecEnv` (multiprocessing).
- **Checkpoints:** `stage10_league_v416.zip`, `stage10_league_latest.zip`

## Stage 11 — Alpha-Beta Punisher & Sparse Rewards ("University")
- **Date:** 2026-04-27 → 2026-04-29
- **Goal:** Eradicate tactical blind spots; force pure checkmate-driven (king-capture) logic.
- **Opponent:** 30% alpha-beta (depth 1), 70% historical league.
- **Reward:** True sparse.
- **Steps:** ~4,000,000 logged (target 10,000,000).
- **Result:** KL divergence stable (~0.007). Frame rate dropped under alpha-beta overhead
  (~107 FPS). Model began exploiting the depth-1 horizon effect.

## Peter Local — Direct engine grounding ("Tactical Grounding")
- **Goal:** Train against the locally-built Peter alpha-beta engine — a *real* tactical opponent.
- **Opponent:** Peter, mixed search depths.
- **Checkpoints:** `models/duck_ppo/peter_local/peter_local_v1..v20.zip`
- **Result:** Strongest checkpoint **`peter_local_v20`** beats Peter depth-2 **100% (20/0/0)**.
- **Key finding:** The stage-10/12 self-play league models **lose 0/20** to Peter depth-2. Pure
  self-play looked strong internally but collapsed against a real engine — the motivation for every
  later Peter-grounded stage.

## "Strong" — 12h Peter + strong self-play ("Consolidation")
- **Date:** 2026-06-03
- **Goal:** A model that is strong vs humans / a strong engine within a 12h budget.
- **Warm-start:** `peter_local_v20`.
- **Opponent mix (8 envs):** 3× Peter depth-2 (tactical anchor) + 5× strong self-play league
  (latest + Peter-trained historical snapshots). Depth-3 banned for speed (~3.4 steps/s gates the
  synchronous `SubprocVecEnv`); depth-1 banned (policy exploits its 1-ply horizon). Every env
  wrapped in `Monitor` so win-rate (`ep_rew_mean`) is logged.
- **Reward:** Sparse terminal.
- **Steps:** 6,356,992 over 11.5h (~153 steps/s avg, ~105 steps/s steady).
- **Bug fixed:** `peter_local.py` passed `numpy.int64` actions into `json.dumps`, crashing Peter
  workers (likely cause of earlier run restarts). Now cast to `int`.
- **Results** (`models/duck_ppo/strong/strong_final.zip`):
  - vs Peter depth-2: **24/0/0** (perfect) — no regression from warm-start.
  - vs `peter_local_v20` head-to-head: **100% both directions** (40/0/0 and 0/40) — strictly
    stronger than the previous best.
  - vs Peter depth-3: **0/16** — the deep-search wall remains.
- **Deployed:** wired into `DuckChess_Game/UI/main.py` as the active game AI *at the time*.
- **Tooling added:** `train_strong.py` (time-bounded run), `eval_vs_peter.py` (ground-truth W/L/D).

## Stage 12 — Final League
- **Goal:** Continue league consolidation; produce the stage-12 weights used to seed later stages.
- **Opponent:** League of stage-11/12 checkpoints.
- **Checkpoints:** `models/duck_ppo/stage 12/stage12_final_v1..v40.zip`
- **Note:** Checkpoint promotion uses numeric sort (fixed in `train_stage12.py`).

## Stage 13 — Peter depth-2 + Stage-12 league
- **Goal:** Combine a real engine anchor with the strongest learned league.
- **Opponent mix (heterogeneous `SubprocVecEnv`):**
  - ~40% `PeterLocalEnv` (depth 2) — the local Peter engine plays every move via the pyo3 bindings;
    each half-move is mirrored to Peter's shadow engine to keep state in sync.
  - ~60% `DuckChessEnvStage13` — `LeagueOpponent` backed by real stage-12 MaskablePPO weights,
    pre-seeded at training start and refreshed with this run's own improving checkpoints.
- **Entry point:** `train_stage13.py`.
- **Status:** Run tooling complete; promote checkpoints only after `eval_vs_peter.py` confirms
  no regression vs depth-2.

## "Anti-exploit" — 1h corrective probe
- **Goal:** Diagnose and start correcting the **king-rush exploit** — the 12h model wins only via a
  ~4-move knight-rush at the enemy king, which beats shallow Peter and other RL models but loses
  0/N to Peter depth-3 and to a thinking human.
- **Approach:** (1) baseline `strong_final` vs Peter depth-3 (win-rate + survival length);
  (2) warm-start from `strong_final` and train 1h vs depth-3 (8 envs, `Monitor`); (3) re-evaluate
  and print a before/after comparison.
- **Reward:** Sparse vs depth-3 (depth-3 defends its king, so the rush fails).
- **Honest expectation:** ~1h at depth-3 is only ~100k steps; the exploit took millions of steps to
  form, so 1h will not fix it. **Survival length vs depth-3** is the sensitive progress signal.
- **Entry point:** `train_antiexploit.py` · **Checkpoint:** `models/duck_ppo/antiexploit/antiexploit_latest.zip`

## "Real" — 14h corrective run
- **Goal:** Break the king-rush exploit and teach genuine positional play.
- **Diagnosis (measured, not assumed):** the existing models win only via the ~4-move king-rush; it
  loses 0/N to Peter depth-3 and to humans, and when the rush is blocked the policy flails and
  loses.
- **Design, each choice tied to a finding:**
  - **Opponent = pure Peter depth-3.** Depth-3 defends its king, so the rush fails and the model is
    forced to find something better. (Mixing in faster depth-2 envs wouldn't add steps — the
    synchronous batch is gated by the slowest env — it would only dilute the signal.)
  - **Dense shaped reward.** Sparse win/loss against an opponent you never beat is a flat −1 with no
    gradient; dense shaping (development, king safety, material, mobility, duck-blocking) gives a
    learning signal on every move even while still losing.
  - `step_penalty = 0` and `king_push_bonus = 0` — both reward the fast king-hunt, so they are off;
    `draw = +0.1` so surviving is strictly better than suiciding.
  - **Warm-start `strong_final` + higher entropy** to pry the policy off its one trick.
- **Budget:** time-bounded to `--hours` (default 14).
- **Entry point:** `train_real.py` · **Checkpoints:** `models/duck_ppo/real/real_v1..v16.zip`,
  `real_final.zip`, `real_latest.zip`
- **Status:** Checkpoints produced; report ground-truth results from `eval_vs_peter.py` once a run
  clears the depth-3 wall.

---

## Open problem: the Peter depth-3 wall

Every model to date tops out at **0 wins vs Peter depth-3**. Depth-3 defends its king well enough
that the learned king-rush never lands, and nothing better has yet formed. Cracking it likely needs
either sustained depth-3 grounding (far more than 1–14h of ~3.4 steps/s training) or a larger
network with more time. Until a checkpoint beats depth-3, the UI ships with `model_path = None`.
