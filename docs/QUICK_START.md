# Duck Chess Web UI - Quick Start

**Get up and running in 2 minutes**

## Installation

```bash
# Clone or navigate to project
cd /path/to/duck_chess

# Install dependencies (one time)
pip install -r requirements.txt

# Start the server
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890

# Open browser
# → http://localhost:7890
```

## That's it! 

Login with any name and play.

---

## Keyboard Shortcuts (in-game)

| Key | Action |
|-----|--------|
| **F** | Flip board |
| **R** | Resign |
| **Esc** | Close modal |

---

## File Structure

```
web_ui/
├── server.py          ← FastAPI backend
├── index.html         ← Frontend (everything in one file)
└── duck.png           ← Asset
```

---

## Key Features

- ✅ Play vs AI model
- ✅ 2-player local
- ✅ Save/load games
- ✅ Replay with board snapshots
- ✅ Per-player timers
- ✅ Move validation feedback
- ✅ Beautiful animations
- ✅ Mobile responsive

---

## Troubleshooting

**"Can't find module"**
→ Run `pip install -r requirements.txt` and check virtual env is activated

**"Port 7890 in use"**
→ Use `--port 8000` or kill process on 7890

**"Models not loading"**
→ Wait 3 seconds for server to fully start

**"AI move is slow"**
→ Normal (0.5-2s). Use faster model (stage9) or try 2-player

---

## Files to Read

| File | Purpose |
|------|---------|
| `requirements.txt` | Dependencies |
| `WEB_UI_SETUP.md` | Detailed setup + troubleshooting |
| `WEB_UI_IMPLEMENTATION_SUMMARY.md` | What was built (15 tasks) |
| `DEMO_GUIDE.md` | How to demo to others |
| `CLAUDE.md` | Project architecture |

---

## API Endpoints (if curious)

```
GET  /                    → Serve index.html
GET  /api/models          → List available models
POST /api/new-game        → Start a new game
POST /api/move-piece      → Make a move
POST /api/place-duck      → Place duck
POST /api/resign          → Resign game
POST /api/save-game       → Save game
GET  /api/saved-games     → List saved games
GET  /api/load-game/{fn}  → Load saved game
```

Interactive docs: http://localhost:7890/docs

---

## Performance

| Operation | Time |
|-----------|------|
| Page load | 1-2s |
| AI move | 0.5-2s |
| Save game | <1s |
| Load game | <1s |

---

## What's Inside

```
15 tasks completed:

Core (8):
✅ Dynamic model loading
✅ 2-player local mode
✅ Board flip
✅ Save/load games
✅ Replay mode
✅ Game-over screen
✅ Move validation feedback
✅ Player names

Polish (7):
✅ Real board states in replay
✅ Network error handling
✅ Move notation
✅ AI thinking animation
✅ Game timers
✅ Splash screen & shortcuts
✅ Smoke tested
```

---

## Next Steps

1. **Run it**: `python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890`
2. **Play**: http://localhost:7890 (login → play)
3. **Save**: Game-over → "Save" button
4. **Replay**: Menu → saved game → "Load & Review"
5. **Demo**: See `DEMO_GUIDE.md`

---

**Status**: Production-ready ✅  
**Lines of Code**: ~3,700  
**Documentation**: 5 files  
**Ready for**: Finals presentation 🎓

---

Questions? See `WEB_UI_SETUP.md` (Q&A section) or `CLAUDE.md` (architecture).
