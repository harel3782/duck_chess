Duck Chess RL Engine
Architecture
Core: Python (Pure Python, no C++).

Algorithm: MaskablePPO (sb3-contrib, stable-baselines3).

Environment Wrapper: Gymnasium.

Framework: PyTorch.

State & Action Space
Observation Space: Box(19, 8, 8, dtype=float32). 19 Bitboards representing piece locations, duck location, and valid action masks.

Action Space: Discrete(4096). Neural network outputs a single integer. Engine decodes integer to (start_row, start_col) and (end_row, end_col).

Training Progression
Early Stages (1-9)
Fundamental mechanics. Legal move generation.

Dense rewards based on material capture and basic positioning.

Stage 10: League Play
Introduced dynamic Self-Play against historical model snapshots.

Optimization for high-mobility and endgame checkmates.

Stage 11: Alpha-Beta Punisher & Sparse Rewards
Opponent Distribution: 30% Alpha-Beta Depth 1 (Greedy tactical execution), 70% RL League (Historical/Latest clones).

Reward Function: True Sparse Rewards. 0.0 for all intermediate steps. +1.0 for Win, -1.0 for Loss.

Logic: Eliminates point-farming exploits. Forces pure checkmate-driven logic. Depth 1 opponent punishes undefended pieces instantly, training the model to be a hyper-aggressive hunter.

Infrastructure & Multiprocessing
Python Runtime
Requirement: Python 3.11 or 3.12.

Constraint: Python 3.13 is unsupported. Causes silent C++ Segmentation Faults during PyTorch MaskablePPO.load() unpickling.

Multiprocessing Engine
Parallelization: SubprocVecEnv. Bypasses Python GIL by allocating each environment to an isolated CPU process.

Chief Worker Architecture: Resolves I/O throttling and duplicate logs. Environments are assigned explicit IDs. Only Worker 0 (Chief) is permitted to write .pkl replay logs to disk.

Checkpointing: Dynamic file retrieval. train.py auto-detects the latest .zip model via creation timestamp and resumes total_timesteps dynamically (reset_num_timesteps=False).

KL Divergence Control: target_kl configured to 0.05 to prevent excessive Early Stopping while maintaining policy stability.

Evaluation & UI Integration
Tool: Playwright (Headless/Headed Chromium).

Environment: DuckPeterEnv custom Gymnasium wrapper.

Inference Pipeline:

PPO Agent predicts action index (0-4095).

HeadlessEngine decodes index to matrix coordinates (r, c).

Bridge logic maps matrices to algebraic coordinates (e.g., "e2", "e4").

Playwright translates algebraic strings to SVG pixel coordinates and physical mouse clicks.

Playwright waits for opponent UI response.

Data scraper reads SVG rect, path (highest opacity arrow), and circle (radius sorting for duck).

Scraped data mapped back to 19x8x8 Bitboards for the next tensor calculation.
