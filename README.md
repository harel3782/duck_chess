🦆 Duck Chess - RL Engine & UI
Pure Python Reinforcement Learning Engine for the "Duck Chess" variant.

⚠️ State: Full RL engine operational. C++ dependencies eliminated. Project built entirely in Python. Final Project for B.Sc. Software Engineering.

📖 Project Core
Duck Chess variant constraints: Players execute standard move, then relocate neutral Duck to empty square. Duck blocks line of sight.
System trains MaskablePPO agent via dynamic self-play league and Alpha-Beta opponent punishing.

🛠️ Tech Stack
Language: Python 3.11 / 3.12 (Python 3.13 unsupported due to PyTorch memory faults).

Algorithm: MaskablePPO (sb3-contrib, stable-baselines3).

Matrix Engine: PyTorch, Numpy.

Environment Wrapper: Gymnasium.

Evaluation Interface: Playwright (Chromium web scraping).

✨ Architecture & Logic
Observation Space: Box(19, 8, 8, dtype=float32). 19 Bitboards mapping pieces, duck location, and legal action masks.

Action Space: Discrete(4096). Single integer output. Engine translates integer to (start_row, start_col) and (end_row, end_col).

Training Mechanics:

Multiprocessing parallelization via SubprocVecEnv bypassing GIL.

Chief Worker topology to isolate I/O operations and .pkl generation.

League Self-Play: Agent trains against dynamic pool of historical model snapshots (Stage 10).

Sparse Rewards: +1.0 Win, -1.0 Loss. Zero intermediate rewards. Forces pure checkmate-driven logic (Stage 11).

Alpha-Beta Punisher: 30% opponent pool utilizes Depth 1 greedy search to punish undefended material.

🚀 Run Instructions
Clone repository:

Bash
	git clone https://github.com/harel3782/YOUR_REPO_NAME.git
Initialize virtual environment (Python 3.11 or 3.12 required):

Bash
	py -3.12 -m venv .venv
	.\.venv\Scripts\activate
Install dependencies:

Bash
	pip install torch stable-baselines3 sb3-contrib pygame playwright tensorboard
	playwright install
Execute training protocol:

Bash
	python -m DuckChess_Game.SBThree.train
Execute Playwright UI evaluation:

Bash
	python -m DuckChess_Game.playwright.eval_vs_peter
