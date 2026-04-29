Duck Chess Training Log
Stage 1: Random Bot ("גן חובה")
Date: 2026-03-15

Target: Learn basic moves and checkmate.

Steps: 100,000 timesteps.

Results: ep_rew_mean reached ~0.9. Completed successfully.

Checkpoint: duck_stage1_final.zip

Env: duck_env_stage1_random.py

Stage 2: Greedy Bot ("יסודי")
Date: 2026-03-27

Target: Learn to defend pieces and handle aggressive captures.

Opponent: Greedy Bot (prioritizes any available capture).

Steps: 500,000 timesteps.

Results: Learned basic material preservation against immediate threats.

Checkpoint: duck_stage2_greedy.zip

Stage 3-8: Dense Reward Scaling & Mechanics ("חטיבת ביניים")
Date: 2026-04-01 - 2026-04-14

Target: Transition to Bitboard architecture, legal move masking optimization, early self-play stability.

Opponent: Fixed previous versions.

Reward: Dense (+ points for material captures).

Steps: ~5,000,000 timesteps combined.

Results: Validated Gymnasium environment logic. Reward function stabilized.

Stage 9: Self-Play Baseline ("מבוא לליגה")
Date: 2026-04-15 - 2026-04-19

Target: Establish strong self-play baseline before dynamic pool generation.

Opponent: Latest self-play clones continuously updating.

Steps: 3,000,000 timesteps.

Checkpoint: stage9_selfplay_latest.zip

Stage 10: League Play ("תיכון")
Date: 2026-04-20 - 2026-04-26

Target: High-mobility, endgame optimization, prevent strategy overfitting (Catastrophic Forgetting).

Opponent: Dynamic League (Random historical snapshots vs Latest).

Steps: 4,000,000 timesteps.

Architecture: SubprocVecEnv (Multiprocessing).

Checkpoint: stage10_league_v416.zip, stage10_league_latest.zip

Stage 11: Alpha-Beta Punisher & Sparse Rewards ("אוניברסיטה")
Date: 2026-04-27 - 2026-04-29 (Ongoing)

Target: Eradicate tactical blind spots. Force pure checkmate-driven logic. Train hyper-aggressive hunter behavior.

Opponent: 30% Alpha-Beta (Depth 1), 70% Historical League.

Reward Structure: True Sparse (0.0 intermediate, +1.0 Win, -1.0 Loss).

Steps: ~4,000,000 timesteps logged (Target: 10,000,000).

Results: KL Divergence stable (0.007). Frame rate dropping due to Alpha-Beta overhead (107 FPS). Model currently exploiting Depth-1 horizon effect.

Checkpoint: models/duck_ppo/stage 11/
