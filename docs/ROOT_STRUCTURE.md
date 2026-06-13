# Root Directory Structure

## Final Organization

```
duck_chess/
├── CLAUDE.md              ← Project guidance (DO NOT MOVE)
├── README.md              ← Project overview
├── requirements.txt       ← Python dependencies
├── pytest.ini             ← Test configuration
├── conftest.py            ← Pytest fixtures (must stay in root)
│
├── docs/                  ← ALL DOCUMENTATION (moved here)
│   ├── INDEX.md           ← Start here for guidance
│   ├── QUICK_START.md
│   ├── WEB_UI_SETUP.md
│   ├── WEB_UI_IMPLEMENTATION_SUMMARY.md
│   ├── DEMO_GUIDE.md
│   ├── WEB_UI_TEST_SUMMARY.md
│   ├── WEB_UI_TEST_PLAN.md
│   └── [9 more documentation files]
│
├── web_ui/                ← Web UI (FastAPI + HTML)
│   ├── server.py
│   ├── index.html
│   └── duck.png
│
├── DuckChess_Game/        ← Game engine
│   ├── Logic/
│   ├── UI/
│   └── SBThree/
│
├── tests/                 ← Test suite (56 tests)
│   ├── test_web_ui_server.py
│   └── test_web_ui_integration.py
│
├── models/                ← Trained RL models
│   └── duck_ppo/
│
├── saved_replays/         ← User-saved games
├── tensorboard_logs/      ← Training logs
├── scripts/               ← Utility scripts
├── assets/                ← Images & resources
└── .archive/              ← Archived files (hidden)
```

## What Was Moved

| From Root | To | Reason |
|-----------|-----|--------|
| QUICK_START.md | docs/ | Documentation |
| WEB_UI_SETUP.md | docs/ | Documentation |
| WEB_UI_IMPLEMENTATION_SUMMARY.md | docs/ | Documentation |
| DEMO_GUIDE.md | docs/ | Documentation |
| WEB_UI_TEST_SUMMARY.md | docs/ | Documentation |
| WEB_UI_TEST_PLAN.md | docs/ | Documentation |
| IMPLEMENTATION_SUMMARY.md | docs/ | Documentation |
| training_log.md | docs/ | Documentation |
| HEADLESS_TRAINING.md | docs/ | Documentation |
| TESTING.md | docs/ | Documentation |
| duck_chess_full_code.txt | .archive/ | Cleanup |

## What Stayed in Root

✅ **Must stay in root:**
- `CLAUDE.md` — Project guidance (referenced by AI systems)
- `README.md` — GitHub project overview
- `requirements.txt` — Pip dependency standard
- `pytest.ini` — Test configuration
- `conftest.py` — Pytest fixtures

## How to Navigate

### For Quick Setup
```bash
# Read this first
cat docs/QUICK_START.md

# Install & run
pip install -r requirements.txt
python -m uvicorn web_ui.server:app --port 7890
```

### For Documentation
See `docs/INDEX.md` for complete guide to all docs

### For Testing
```bash
pytest tests/ -v
```

## Result

✅ **Root files reduced from 12 to 5**  
✅ **All docs organized in `docs/` folder**  
✅ **Clean, professional structure**  
✅ **Easy to navigate**

