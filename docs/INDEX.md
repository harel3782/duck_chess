# Duck Chess Documentation Index

Everything under `docs/`, grouped by purpose. Project-level entry points
([README.md](../README.md), [CLAUDE.md](../CLAUDE.md), [PLAN_V2.md](../PLAN_V2.md)) live in the repo
root.

## Start here
- **[../README.md](../README.md)** — Project overview and quick start
- **[QUICK_START.md](QUICK_START.md)** — Get the web UI running in ~2 minutes
- **[../CLAUDE.md](../CLAUDE.md)** — Architecture and commands (for AI assistants and humans)

## Setup & running
- **[WEB_UI_SETUP.md](WEB_UI_SETUP.md)** — Full web-UI setup, requirements, and troubleshooting
- **[../requirements.txt](../requirements.txt)** — Pinned Python dependencies
- **[ROOT_STRUCTURE.md](ROOT_STRUCTURE.md)** — Where everything lives in the repo

## Web UI
- **[WEB_UI_IMPLEMENTATION_SUMMARY.md](WEB_UI_IMPLEMENTATION_SUMMARY.md)** — What the web UI does (feature breakdown)
- **[DEMO_GUIDE.md](DEMO_GUIDE.md)** — 10-minute demo script for the finals presentation

## Testing
- **[TESTING.md](TESTING.md)** — How to run every test layer + the real pass/fail status (canonical)
- **[WEB_UI_TEST_PLAN.md](WEB_UI_TEST_PLAN.md)** — Formal web-UI test specification / roadmap
- **[E2E_TESTS.md](E2E_TESTS.md)** — Playwright end-to-end test blueprint
- **[STP-DUCK-001.md](STP-DUCK-001.md)** — Formal Software Test Plan (engine + RL)
- **[STD-DUCK-001.md](STD-DUCK-001.md)** — Formal Software Test Design (20 critical cases)

## Training & AI
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** — Build status at a glance
- **[HEADLESS_TRAINING.md](HEADLESS_TRAINING.md)** — Long, unattended training runs
- **[training_log.md](training_log.md)** — Stage-by-stage training history and results
- **[../PLAN_V2.md](../PLAN_V2.md)** — The v2 + search + Expert-Iteration plan and its central lesson

---

## Repo layout (abridged)

```
duck_chess/
├── README.md / CLAUDE.md / PLAN_V2.md   ← root entry points
├── requirements.txt · pytest.ini · conftest.py
├── docs/                 ← this folder
│   └── INDEX.md          ← you are here
├── web_ui/               ← FastAPI + HTML web app (server.py, index.html, duck.png)
├── DuckChess_Game/
│   ├── Logic/            ← game engine
│   ├── UI/               ← Pygame desktop app
│   └── SBThree/          ← RL training, MCTS, evaluation
├── models/duck_ppo/      ← trained checkpoints
└── tests/                ← pytest suite (engine, RL, web, e2e)
```

---

## Quick commands

```bash
# Desktop game
python DuckChess_Game/UI/main.py

# Web UI  →  http://localhost:7890
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890

# Tests (engine + RL core is fast and headless; see TESTING.md for the optional layers)
pytest
```
