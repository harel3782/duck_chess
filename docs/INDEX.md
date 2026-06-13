# Duck Chess Documentation Index

## Quick Start
- **[QUICK_START.md](QUICK_START.md)** — Get running in 2 minutes

## Setup & Installation
- **[WEB_UI_SETUP.md](WEB_UI_SETUP.md)** — Complete setup guide with troubleshooting
- **[requirements.txt](../requirements.txt)** — Python dependencies

## Web UI
- **[WEB_UI_IMPLEMENTATION_SUMMARY.md](WEB_UI_IMPLEMENTATION_SUMMARY.md)** — What was built (15 tasks)
- **[DEMO_GUIDE.md](DEMO_GUIDE.md)** — 10-minute demo script for finals
- **[WEB_UI_TEST_SUMMARY.md](WEB_UI_TEST_SUMMARY.md)** — 56 passing tests, coverage report

## Testing
- **[WEB_UI_TEST_PLAN.md](WEB_UI_TEST_PLAN.md)** — Test strategy and categories
- **[TESTING.md](TESTING.md)** — How to run tests

## Training & AI
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** — Overall project summary
- **[HEADLESS_TRAINING.md](HEADLESS_TRAINING.md)** — Headless training guides
- **[training_log.md](training_log.md)** — Training history and notes

## Reference
- **[../CLAUDE.md](../CLAUDE.md)** — Project architecture and guidance (in root)
- **[../README.md](../README.md)** — Project overview (in root)

---

## File Organization

```
duck_chess/
├── CLAUDE.md              ← Project guidance (keep in root)
├── README.md              ← Project overview (keep in root)
├── requirements.txt       ← Dependencies (keep in root)
├── docs/                  ← All documentation
│   └── INDEX.md           ← This file
├── web_ui/                ← Web UI (FastAPI + HTML)
│   ├── server.py
│   ├── index.html
│   └── duck.png
├── DuckChess_Game/        ← Game engine & training
│   ├── Logic/
│   ├── UI/
│   └── SBThree/
├── models/                ← Trained models
│   └── duck_ppo/
├── tests/                 ← Test suite (56 tests)
│   ├── test_web_ui_server.py
│   └── test_web_ui_integration.py
└── [other directories]
```

---

## For Demos

Start here: [DEMO_GUIDE.md](DEMO_GUIDE.md)

Then run: 
```bash
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
```

Open: http://localhost:7890

---

## For Setup

Start here: [WEB_UI_SETUP.md](WEB_UI_SETUP.md)

---

## For Testing

```bash
pytest tests/test_web_ui_server.py tests/test_web_ui_integration.py -v
```

See: [WEB_UI_TEST_SUMMARY.md](WEB_UI_TEST_SUMMARY.md)

---

**Last updated**: June 14, 2026
