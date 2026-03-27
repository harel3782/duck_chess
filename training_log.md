# Duck Chess Training Log

## Stage 1: Random Bot ("גן חובה")
- **Target**: Learn basic moves and checkmate.
- **Steps**: 100,000 timesteps.
- **Results**: ep_rew_mean reached ~0.9. Completed successfully.
- **Checkpoint**: `duck_stage1_final.zip`
- **Env**: `duck_env_stage1_random.py`

## Stage 2: Greedy Bot ("יסודי")
- **Date**: 2026-03-27
- **Target**: Learn to defend pieces and handle aggressive captures.
- **Opponent**: Greedy Bot (prioritizes any available capture).