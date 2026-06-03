# Duck Chess AI - Training Log

## Stage 1: Random Bot ("Kindergarten")
*	Date: 2026-03-15
*	Target: Learn basic moves and checkmate.
*	Steps: 100,000 timesteps.
*	Results: ep_rew_mean reached ~0.9. Completed successfully.
*	Checkpoint: `duck_stage1_final.zip`
*	Env: `duck_env_stage1_random.py`

## Stage 2: Greedy Bot ("Elementary")
*	Date: 2026-03-27
*	Target: Learn to defend pieces and handle aggressive captures.
*	Opponent: Greedy Bot (prioritizes any available capture).
*	Steps: 500,000 timesteps.
*	Results: Learned basic material preservation against immediate threats.
*	Checkpoint: `duck_stage2_greedy.zip`

## Stage 3-8: Dense Reward Scaling & Mechanics ("Middle School")
*	Date: 2026-04-01 - 2026-04-14
*	Target: Transition to Bitboard architecture, legal move masking optimization, early self-play stability.
*	Opponent: Fixed previous versions.
*	Reward: Dense (+ points for material captures).
*	Steps: ~5,000,000 timesteps combined.
*	Results: Validated Gymnasium environment logic. Reward function stabilized.

## Stage 9: Self-Play Baseline ("League Intro")
*	Date: 2026-04-15 - 2026-04-19
*	Target: Establish strong self-play baseline before dynamic pool generation.
*	Opponent: Latest self-play clones continuously updating.
*	Steps: 3,000,000 timesteps.
*	Checkpoint: `stage9_selfplay_latest.zip`

## Stage 10: League Play ("High School")
*	Date: 2026-04-20 - 2026-04-26
*	Target: High-mobility, endgame optimization, prevent strategy overfitting (Catastrophic Forgetting).
*	Opponent: Dynamic League (Random historical snapshots vs Latest).
*	Steps: 4,000,000 timesteps.
*	Architecture: SubprocVecEnv (Multiprocessing).
*	Checkpoint: `stage10_league_v416.zip`, `stage10_league_latest.zip`

## Stage 11: Alpha-Beta Punisher & Sparse Rewards ("University")
*	Date: 2026-04-27 - 2026-04-29 (Ongoing)
*	Target: Eradicate tactical blind spots. Force pure checkmate-driven logic. Train hyper-aggressive hunter behavior.
*	Opponent: 30% Alpha-Beta (Depth 1), 70% Historical League.
*	Reward Structure: True Sparse (0.0 intermediate, +1.0 Win, -1.0 Loss).
*	Steps: ~4,000,000 timesteps logged (Target: 10,000,000).
*	Results: KL Divergence stable (0.007). Frame rate dropping due to Alpha-Beta overhead (107 FPS). Model currently exploiting Depth-1 horizon effect.

## Peter Local: Direct engine training ("Tactical Grounding")
*	Target: Train against the locally-built Peter alpha-beta engine (real tactical opponent).
*	Opponent: Peter engine, mixed search depths.
*	Checkpoints: `models/duck_ppo/peter_local/peter_local_v1..v20.zip`
*	Results: Strongest checkpoint **peter_local_v20** beats Peter depth-2 at 100% (20/0/0).
	Key finding: the stage-10/12 self-play league models LOSE 0/20 to Peter depth-2 —
	pure self-play looked strong internally but collapsed against a real engine.

## Stage "Strong": 12h Peter + strong self-play ("Consolidation")
*	Date: 2026-06-03
*	Target: A model that is very strong vs humans / a strong engine, in a 12h budget.
*	Warm-start: `peter_local_v20`.
*	Opponent mix (8 envs): 3x Peter depth-2 (tactical anchor) + 5x strong self-play
	league (latest + Peter-trained historical snapshots). Depth-3 banned for speed
	(it runs at ~3.4 steps/s and gates the synchronous SubprocVecEnv); depth-1 banned
	(policy exploits its 1-ply horizon). Every env wrapped in `Monitor` so win-rate
	(`ep_rew_mean`) is finally logged.
*	Reward: Sparse terminal (+1 win / -1 loss / +0.1 draw).
*	Steps: 6,356,992 over 11.5h (~153 steps/s avg, ~105 steps/s steady).
*	Bug fixed: `peter_local.py` passed numpy.int64 actions into `json.dumps`,
	crashing Peter workers (likely cause of earlier run restarts). Now cast to int.
*	Results (`models/duck_ppo/strong/strong_final.zip`):
	- vs Peter depth-2: **24/0/0** (perfect) — no regression from warm-start.
	- vs peter_local_v20 head-to-head: **100% both directions** (40/0/0 and 0/40).
	  -> Strictly stronger than the previous best.
	- vs Peter depth-3: 0/16 — the deep-search wall remains (would need depth-3
	  grounding or a larger network + more time to crack).
*	Deployed: wired into `DuckChess_Game/UI/main.py` as the active game AI.
*	Tooling added: `train_strong.py` (time-bounded run), `eval_vs_peter.py`
	(ground-truth W/L/D vs the engine — the metric the earlier runs lacked).
