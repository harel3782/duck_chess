# Repository Structure

Where everything lives. The repo root holds three entry-point docs and the test/dependency config;
everything else is organized into directories.

```
duck_chess/
├── README.md              ← Project overview (keep in root)
├── CLAUDE.md              ← Guidance for AI assistants (keep in root)
├── PLAN_V2.md             ← v2 + search + Expert-Iteration plan and results
├── requirements.txt       ← Pinned Python dependencies
├── pytest.ini             ← Test configuration (testpaths = tests)
├── conftest.py            ← Pytest fixtures / headless SDL setup (must stay in root)
│
├── docs/                  ← All other documentation (see INDEX.md)
│   ├── INDEX.md           ← Index of this folder — start here
│   ├── QUICK_START.md
│   ├── WEB_UI_SETUP.md
│   ├── WEB_UI_IMPLEMENTATION_SUMMARY.md
│   ├── DEMO_GUIDE.md
│   ├── TESTING.md
│   ├── WEB_UI_TEST_PLAN.md
│   ├── E2E_TESTS.md
│   ├── HEADLESS_TRAINING.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   ├── training_log.md
│   ├── STP-DUCK-001.md    ← Formal Software Test Plan (+ .txt / .wd.docx siblings)
│   └── STD-DUCK-001.md    ← Formal Software Test Design (+ .txt / .wd.docx siblings)
│
├── web_ui/                ← FastAPI + HTML web app
│   ├── server.py
│   ├── index.html
│   └── duck.png
│
├── DuckChess_Game/        ← Game engine + UI + RL
│   ├── Logic/             ← Pure-Python engine (rules, bitboards, RL bridge)
│   ├── UI/                ← Pygame desktop app
│   └── SBThree/           ← RL training, MCTS, evaluation
│
├── tests/                 ← Pytest suite (engine, RL, web UI, e2e/visual)
├── models/duck_ppo/       ← Trained RL checkpoints, by stage/run
├── logs/                  ← Training logs and CSV progress
├── tensorboard_logs/      ← TensorBoard event files
├── saved_replays/         ← User-saved games
├── scripts/               ← Utility scripts (build launcher, replay viewers, debug)
└── assets/                ← Images, sounds, rules text
```

## What must stay in the root

| File | Why |
|------|-----|
| `README.md` | GitHub project overview |
| `CLAUDE.md` | Referenced by AI assistants |
| `PLAN_V2.md` | Self-contained plan; handed to new sessions |
| `requirements.txt` | Pip dependency standard |
| `pytest.ini` | Test configuration |
| `conftest.py` | Pytest fixtures (sets headless SDL drivers before pygame imports) |

## How to navigate

- **Setup / run:** [QUICK_START.md](QUICK_START.md) (web UI) or [../README.md](../README.md) (both UIs)
- **All docs:** [INDEX.md](INDEX.md)
- **Tests:** [TESTING.md](TESTING.md) — `pytest` from the repo root
- **Training history & plan:** [training_log.md](training_log.md), [../PLAN_V2.md](../PLAN_V2.md)
