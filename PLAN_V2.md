# Plan v2 — Peter-grounded training + n-step search (incl. duck)

Self-contained plan. Give this file to any new session to continue the work.

## Status (updated 2026-06-12 night)

- [x] Step 0 — baseline: real_latest vs Peter d2 = 6/4/0 (60%), vs d3 = 0/6/4 (score 0.200)
- [x] Step 1 — `duck_env_v2.py` (PoolEnv) + `train_peter_v2.py` written
- [x] Step 2 — smoke test passed (all 6 pool opponents sampled, CSV/checkpoints/league refresh OK, 277 tests pass)
- [x] Step 3 — DONE. Old run exited 04:50; v2 auto-launched 04:51 (PID 37364),
      12h budget; finished ~17:14 at ~670k steps. v2_final.zip saved. At 380k steps / ~4.5h the per-opponent W/L/D shows the
      HEALTHY, non-exploit signature we wanted (this is the whole point of v2):
        * vs Peter d2: 2/94 (2%) -> 52/57 (~48%) win rate — and from RANDOM
          starts mixed in a pool, so it is general play, NOT the 4-move rush.
        * vs random:  26/28 -> 54/6   (early fresh model was genuinely weak;
          now competent across the board)
        * vs sp_hist: 3/43 -> 47/8    (learned to DEFEND the old rush seeds)
        * vs sp_latest: 6/140 -> 122/40
        * vs Peter d3: still ~0 (the wall — expected; search is meant for this)
        * ep_rew_mean -0.86 -> -0.10 steadily; entropy_loss -3.29 -> -2.54
          GLIDING down (no sudden crash = no exploit); explained_variance 0.71
          (the sparse value head is well-calibrated — exactly what search needs).
      Watch: `logs/v2_train.log`, `logs/v2_progress.csv`, `models/duck_ppo/v2/`

      v2 value head calibrated: start V=-0.07 (old=+3.9 saturated). Step 6 heavy
      search battery DEFERRED until training finishes (~16:51) per "avoid heavy
      concurrent evals" — eval_search is ~2.7s/turn and would fight the trainer.
      HELD-OUT clean eval (eval_vs_peter, standard start), vs Peter d2:
        * v2_v4 (@~280k) = 10/2/0 = 83%
        * v2_v5 (@~480k) = 11/1/0 = 92%   (still climbing — beats old base 60%)
      Both general play (random starts + pool + sparse reward), NOT the rush.
- [x] Step 4 — `eval_anchors.py` written. v2_final raw anchor ladder (12 games):
      random 1.00 | greedy 0.25 | alphabeta 0.67 | peter_d1 0.75 | peter_d2 0.92
      | peter_d3 0.00  ->  Anchor Elo 1025.
      Blind spot: loses to the simple `greedy` bot (3/9) despite crushing the far
      stronger Peter d2 — `greedy` was not in the training pool. Non-transitive;
      fix = add GreedyOpponent to the v2 pool next run.

=== STEP 6 RESULTS (v2_final, the trained-from-scratch v2 model) ===

      | config                              | vs Peter d2      | vs Peter d3     |
      |-------------------------------------|------------------|-----------------|
      | RAW policy (20 games)               | 19/1/0  = 95%    | 0/20/0 = 0%     |
      | + search value sample-veto m=0.2    | 0/20/0  = 0%     | 0/18/2 = 5%(dr) |

      VERDICT: the RAW v2 model is the deliverable — first GENERAL model that
      crushes Peter d2 (95%, baseline was 60% via the rush) without exploiting.
      Search as built HURTS: it cratered d2 95% -> 0%. Diagnosis (debug_search
      on v2_final): search MECHANICS are correct (finds forced king capture
      +1002; evades a rook threat with a duck block), value head calibrated
      (start +0.34). The problem is that in QUIET positions all macros score in a
      narrow band (~+0.6..+0.73) the PPO value head cannot rank, so value-driven
      OVERRIDES replace the policy's deliberate winning moves with value-noise.
      The policy IS the strength; the PPO critic is a poor differential
      evaluator off-distribution.

      CONTROLLED TEST (6 games vs d2) confirms it conclusively:
        * sample-veto margin=5.0 (search defers to policy ~always) -> 6/0/0 100%
        * mode=best (always play value-argmax)                     -> 0/6/0   0%
      => no search bug; the PPO value head simply must not drive move selection.

- [x] Step 5/6 DONE. DELIVERABLE = raw v2_final, now wired into the UI
      (DuckChess_Game/UI/main.py model_path = models/duck_ppo/v2/v2_final.zip;
      set to None to revert to the alpha-beta AI). search.py works mechanically
      (n-ply incl. duck) but needs an ExIt-trained value to help — see Step 7.

- [~] Step 7a — VALUE DISTILLATION (round 1 of ExIt; the smart-first move).
      New scripts: gen_value_data.py (raw policy vs Peter d2/d3, records every
      move_piece-phase position -> eventual outcome; MUST use ForcedKingCaptureMask
      or the agent looks crippled — bug found & fixed), finetune_value.py
      (regress ONLY the value head onto outcomes, policy FROZEN). Dataset:
      12,093 positions. Result: value head sign-accuracy 0.65 -> 0.98 (the
      original PPO critic barely beat a coin flip — quantifies why search hurt).
      Policy verified byte-for-byte identical after retrain (logits diff 0.0).
      Output: models/duck_ppo/v2/v2_value.zip. Decisive search test
      (mode=best with retrained value, vs d2/d3) IN PROGRESS.

=== STEP 7 RESULT: SEARCH NOW WORKS (via MCTS) ===

      All configs below use v2_value (policy frozen = raw, value head distilled):

      | engine / config                 | vs Peter d2     | vs Peter d3   |
      |---------------------------------|-----------------|---------------|
      | raw policy                      | ~90% (19/1)     | 0% (0/20)     |
      | alpha-beta mode=best (greedy)   | 0% (0/12)       | 0% (0/12)     |
      | alpha-beta sample-veto m=0.5    | 0% (0/11/1)     | (n/a)         |
      | MCTS sims=200 (PUCT)            | 100% (12/0) ✅  | 0% (0/12)     |

      THE LESSON (project-worthy): a value head is for EVALUATING, the policy is
      for CHOOSING. Value-greedy / veto throw away the policy's move skill and
      collapse (0%). Only AlphaZero-style PUCT MCTS — policy priors guide which
      moves to explore, distilled value scores leaves, integrated over many
      simulations — makes lookahead HELP: it matches/beats raw vs d2 and is fast
      (~0.9s/turn at 200 sims). Value distillation (7a) was the prerequisite:
      MCTS with the raw PPO value head would not work (value sign-acc was 0.65).
      mcts.py also force-plays available king captures (root shortcut + internal
      prior floor) since the policy gives them ~0 prior.
      d3 wall: 0 at sims=200 AND 0/16 at sims=1200 (6x sims, c_puct=2.5). The
      wall holds — inference search alone cannot crack d3 on the current
      policy/value. Cracking d3 requires Step 7b (retraining), not more search.

- [ ] Step 7b (to crack d3) — full Offline Expert Iteration. Now well-founded:
      MCTS (mcts.py) is a working improvement operator (100% d2). The loop:
      (1) self-play / vs-Peter games where the agent moves WITH MCTS, recording
          (state -> MCTS visit-count policy target, game outcome);
      (2) fine-tune the POLICY on the MCTS visit distributions (not just argmax)
          and the VALUE on outcomes (extend finetune_value.py to also train the
          policy head, or do a fresh MaskablePPO-style supervised pass);
      (3) the stronger net guides better MCTS -> repeat.
      This is the standard AlphaZero loop and the realistic route to d3.
      Expensive (MCTS self-play ~0.9s/move). Also add GreedyOpponent to the v2
      pool (duck_env_v2.py DEFAULT_POOL_WEIGHTS) to fix the greedy blind spot.

## DELIVERABLES (final)

- models/duck_ppo/v2/v2_final.zip — the general v2 policy (90% vs Peter d2, no
  exploit, Elo ~1025). Wired into the UI.
- models/duck_ppo/v2/v2_value.zip — same policy + distilled value head
  (sign-acc 0.98). The backbone for search.
- mcts.py + v2_value + MCTS = the strongest agent (100% vs Peter d2, ~0.9s/turn).
- Scripts: duck_env_v2.py, train_peter_v2.py, search.py, mcts.py,
  gen_value_data.py, finetune_value.py, eval_search.py, eval_anchors.py.
- DECISION TAKEN: MCTS+v2_value is WIRED into the UI as the in-game opponent
  (DuckChess_Game/UI/main.py: model_path=v2_value.zip, USE_MCTS=True, sims=200;
  DuckChess_Game/Logic/turn_manager.py ai_turn runs MCTS on a headless_snapshot
  of the live game, plays piece then the stashed duck). Fallbacks: USE_MCTS=False
  -> raw policy; model_path=None -> alpha-beta ai.py. 277 tests pass; flow
  verified headlessly (MCTS beat Peter d2 in the sim). avg ~0.9s/move.
- Step 7b ExIt (for d3): DEFERRED by user ("not now"). Plan above stands.
- [x] Step 5 — `search.py` written; bench: depth=2, ~3s/turn, 1320 nodes
- [~] Step 6 — `eval_search.py` written. Search mechanics verified correct by
      scripts/debug_search.py (finds king captures; evades a rook threat with
      king move + duck block at depth 2). Results on the OLD dense-reward
      baseline checkpoint (10 games per cell, W/L/D, score):

      | config                          | vs Peter d2       | vs Peter d3       |
      |---------------------------------|-------------------|-------------------|
      | raw policy (stochastic)         | 6/4/0   0.600     | 0/6/4   0.200     |
      | search leaf=value               | 0/10/0  0.000     | 0/10/0  0.000     |
      | search leaf=material, mode=best | 0/5/5   0.250     | 0/5/5   0.250     |
      | search leaf=material, mode=veto | 0/7/3   0.150     | 0/10/0  0.000     |
      | search material, sample-veto    | 0/10/0  0.000     | 1/9/0   0.100*    |

      *the single d3 "win" followed 4 Peter engine panics (random fallbacks) —
      not a clean win. Treat search-on-old-checkpoint as a NULL result: the
      dense-reward backbone has no value signal for search to exploit. The real
      test of search is on the v2 model (Step 6 redo, below).

      Findings: (1) the old checkpoint's value head is SATURATED (start pos
      V=+3.9 -> tanh 0.999) — it predicts shaped-reward accumulation, not win
      probability, so leaf='value' misleads the search; the v2 sparse model is
      the intended backbone. (2) material leaf gives tactical safety (half the
      d3 games become draws — slightly above raw's d3 score) but cannot WIN.
      (3) deterministic veto collapses play into one line per color — worse
      than stochastic raw; hence mode='sample-veto' (sample the macro like raw
      play, search only vetoes provable blunders).
- [ ] Step 7 — optional ExIt round

## Context (why v2)

All previous models (stages 1-13, strong, real) hit the same wall: they beat Peter
depth-2 via a narrow "king-rush" exploit but score **0 wins vs Peter depth-3**.
Root causes (confirmed by research + literature):

1. **Opponent monoculture** — training vs a single fixed Peter depth lets PPO learn
   an exploit of that exact opponent instead of general strength.
2. **Fixed starting position** — a memorized opening line is a valid "solution".
3. **Dense shaped reward** (train_real.py) — the agent can farm shaping terms
   instead of winning; it also ruins the value head as a win-probability estimator.
4. **No lookahead** — Peter is itself an AlphaZero-style engine (search + net);
   our model plays with a 0-ply horizon, which depth-3 punishes tactically.

v2 fixes 1-3 in training and 4 with an inference-time search layer that looks
n plies ahead **including duck placements**.

## Steps

### Step 0 — Baseline (so improvement is measurable)
- Evaluate the current best checkpoint (`models/duck_ppo/real/real_latest.zip`)
  vs Peter d2 and d3 with `eval_vs_peter.py`.
- **Expected outcome:** numbers close to the known pattern (high win rate d2,
  ~0% d3). These are the numbers v2 must beat.

### Step 1 — New training pipeline `train_peter_v2.py`
New env wrapper + script with:
- **Per-episode opponent sampling** from a pool: Peter depth 1/2/3 (~50%),
  self-play vs latest checkpoint (~30%), historical checkpoints + random mover
  (~20%). Pool weights configurable.
- **Randomized starting positions**: ~40% of episodes begin after k random legal
  plies (k in 4..16) so memorized openings don't work.
- **Sparse terminal reward** (win +1 / loss -1 / draw 0) + ForcedKingCaptureMask.
  No dense shaping — this also makes the value head a calibrated win-probability
  estimator, which Step 5's search needs.
- **Fresh model by default** (no inherited king-rush prior); `--warm-start` flag
  exists if continuing from a checkpoint is ever wanted.
- Entropy + per-opponent win-rate logging (CSV + TensorBoard). Entropy crash +
  win-rate spike vs one opponent = exploit alarm.
- **Expected outcome:** a runnable script; correctness verified by smoke test.

### Step 2 — Smoke test (15-30 min run)
- Short run, then check: steps/s reasonable (>= ~10), checkpoints save, CSV logs
  written, all opponent types actually sampled, no Peter panics/mask fallbacks
  beyond rare counts.
- **Expected outcome:** green light for the long run. Reward mean will still be
  ~negative — that is normal for a fresh model.

### Step 3 — Long training run (12-24h, background)
- Launch `train_peter_v2.py` headless in the background; checkpoints every 200k
  steps to `models/duck_ppo/v2/`.
- Monitor: ep_rew_mean trend, entropy, win rate vs each pool member.
- **Expected outcome:** steady (not spiky) improvement vs d1 then d2.
  Success criterion at this stage is NOT beating d3 raw — it is general,
  non-exploit play: wins vs d2 from random starts, longer survival vs d3,
  no entropy collapse.

### Step 4 — Anchor evaluation `eval_anchors.py`
- Evaluate checkpoints vs a fixed anchor set never used for that checkpoint's
  gradient updates: random mover, greedy material bot, Peter d1/d2/d3.
- Report W/L/D per anchor + a small Elo estimate. (Optional extra anchor:
  Fairy-Stockfish with wallingRule=duck, needs separate download/compile.)
- **Expected outcome:** an honest strength number per checkpoint; pick the best
  checkpoint by anchor Elo, not by training-opponent win rate.

### Step 5 — n-step search `search.py` (the "see n steps forward" part)
Inference-time lookahead on top of any checkpoint's policy + value heads:
- Tree factored exactly like the game: piece-move node -> duck-move node ->
  opponent piece node -> opponent duck node. n = plies (n=2 is my move+duck,
  n=4 adds opponent's full turn, etc.).
- **Branching control** (this is what makes duck search feasible):
  piece moves pruned to top-k by policy prior; duck moves pruned to top-k duck
  candidates = policy prior top squares + heuristic blockers (block opponent's
  best reply / sliding lines to our king).
- Leaf evaluation = the model's value head; terminal nodes use the real rules
  (king capture wins, **no-legal-moves WINS = fowling**, 50-move = draw).
- Alpha-beta over this tree; state advanced by cloning the engine (no undo in
  the engine). Levels: n=2 greedy first, then general n.
- **Expected outcome:** measurable strength jump at n=2-4; especially vs depth-3
  Peter, because search compensates exactly for the 0-ply tactical horizon.

### Step 6 — Evaluate model+search vs Peter
- Same protocol as Step 4 but with search at n=2 and n=4 vs Peter d2/d3,
  compared against the raw policy.
- **Expected outcome / success criteria:** raw < +search; target is the first
  nonzero win rate vs Peter d3. If d3 wins appear, wire the best (model, n)
  into the UI (`DuckChess_Game/UI/main.py` model_path).

### Step 7 (optional) — Offline Expert Iteration round
- Generate games where the agent plays WITH search; fine-tune the policy on the
  search-chosen moves (and value on outcomes); re-run Step 6.
- Only do this if Step 6 shows search > raw and time remains.

## Operational notes
- Use `.venv\Scripts\python.exe`, run as modules (`-m DuckChess_Game.SBThree...`).
- Peter depths: d1 ~1ms, d2 ~6ms, d3 ~15ms per move; SubprocVecEnv is synchronous,
  so per-episode depth sampling keeps env speeds balanced.
- An older `train_real` 14h run may be active until ~2026-06-13 04:40; do not run
  two trainings at once.
- Always `pytest` after touching `DuckChess_Game/Logic/`.
