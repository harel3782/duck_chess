# Duck Chess Web UI - Quick Demo Guide

**For a 10-minute demo at finals**

---

## Pre-Demo Setup (5 minutes before)

```bash
# 1. Start the server
cd /path/to/duck_chess
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890

# 2. Wait for: "Application startup complete"

# 3. Open browser to: http://localhost:7890
# You should see the splash screen (Duck Chess with duck image)
```

---

## Demo Script (~10 minutes)

### Minute 0-1: Intro & Splash
- Point out the splash screen fading in
- Mention: "Built with FastAPI backend + browser frontend"
- Browser tab shows duck favicon

### Minute 1-2: Authentication & Menu
- Login with name "Demo Player"
- Point out:
  - Model dropdown (dynamically loaded from API)
  - Game options: Play as White, Play as Black, 2 Players
  - Empty saved games section with duck image

### Minute 2-5: Play vs AI
- Click "Play as White" vs strongest model (stage11)
- **Make 5 moves** (have a strategy ready):
  - Move 1: e2 → e4 (white pawn)
  - Move 2: (duck placement)
  - Move 3: Nf3 (knight)
  - Move 4: (duck placement)
  - Move 5: d4 (pawn)

**Point out during play:**
- Timer counting up on human side
- AI thinking animation (pulsing dots + opponent card pulse)
- Move notation in history sidebar (readable: "e2 → e4")
- Flip board with **F key** or "↕" button

### Minute 5-7: Resignation & Save
- Press **R key** to resign (or click resign button)
- Game-over modal appears, showing:
  - ✅ Result: "You Lost"
  - ✅ Reason: "Your king was captured"
  - ✅ Material count: "You were behind by 5 material"
  - ✅ **Timers**: "Time: 02:34 vs 01:12"
- Click "Save" button
- Type game name: "Demo Game"
- Show the success state: "✅ Saved!"

### Minute 7-9: Replay Mode
- Click "Back to Menu"
- Show "My Saved Games" section with the saved game card
- Click "Load & Review"
- Replay controls appear at bottom
- Click **"Next"** a few times:
  - Board updates at each step
  - Move counter shows position (e.g., "5/10")
  - Move notation in history updates
- Press **"▶ Play"**:
  - Auto-steps through all moves at 1.5s intervals
  - Show it completing automatically
- Press **"Exit"** to return to menu

### Minute 9-10: Quick Features Tour
- Show 2-Player mode (start a game, make 1 move each, resign to show error feedback)
- Try **illegal move**: Watch the red flash + error message appear
- Press **Escape** to close any modals (keyboard shortcut)
- Mention: "All game data automatically saved as JSON, can download offline"

---

## Key Talking Points

### Unique Features
- ✅ **Replay system**: Every move stored and visualized
- ✅ **Board snapshots**: Shows exact position after each move (not just final state)
- ✅ **Thinking animation**: AI doesn't look frozen while computing
- ✅ **Per-player timers**: Track how long each side is thinking
- ✅ **Offline fallback**: Can download games if server unavailable
- ✅ **Mobile responsive**: Works on phones too

### Architecture
- ✅ **Single HTML file**: No build process, easy to deploy
- ✅ **FastAPI backend**: Modern Python framework
- ✅ **Shared game logic**: Uses same engine as Pygame UI
- ✅ **RL models**: Trained via MaskablePPO (Stable Baselines3)

### Why This Matters
- 🎓 Full-stack implementation: frontend → backend → game logic
- 🤖 Real AI: Not a heuristic bot, but trained RL model
- 🏆 Polish: Production-quality UI with error handling & recovery
- 📱 Accessible: Works on any browser, any device

---

## Troubleshooting During Demo

| Issue | Fix | Time |
|-------|-----|------|
| Server won't start | Check port 7890 is free; use `--port 8000` | 30s |
| Models don't load | Server not fully started; wait 3s | 10s |
| Board unresponsive | Might be AI thinking; watch timer | 3s |
| Save fails | Click "Retry"; shows network resilience | 5s |
| Keyboard shortcut doesn't work | Try again or use button | 5s |

---

## What NOT to do in Demo

- ❌ Don't play out a full 30-move game (too slow)
- ❌ Don't explain the Duck Chess rules in detail (see in-app rules modal)
- ❌ Don't try to play multiple games (demo only 10 min)
- ❌ Don't mention limitations (focus on what works)
- ❌ Don't go off-script into code details

---

## Post-Demo Follow-Up

If asked:

**"Can you play online with friends?"**
→ "Currently local only, but the architecture supports it. Would need WebSocket upgrade."

**"How strong is the AI?"**
→ "Trained via self-play + curriculum. Beats basic alpha-beta, loses to chess engines (expected)."

**"Can you export games?"**
→ "Yes! JSON format, or download from browser. Could export to PGN (standard chess notation) with minor work."

**"How long did this take?"**
→ "15 tasks over ~6 hours: 8 core features + 7 polish/fixes."

---

## Backup Plans

If something breaks during demo:

**Option A: Restart server**
```bash
# Kill with Ctrl+C
# Run again: python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
```

**Option B: Switch to different game**
- If vs-AI is slow, demo 2-Player local instead (faster)
- If save fails, demo offline download instead

**Option C: Show code**
- Open `web_ui/server.py` or `web_ui/index.html`
- Point out the snapshot generation or replay logic
- Shows the technical depth

---

## Success Metrics

✅ Demo is successful if:
1. Splash screen fades nicely
2. Game loads and AI moves smoothly
3. Timers display and count
4. Save completes with success state
5. Replay mode steps through moves correctly
6. At least one keyboard shortcut works

---

## Slide Template (if presenting)

```
Slide 1: Title
- Duck Chess Web UI
- Built with FastAPI + HTML5
- Full-stack RL project

Slide 2: Features
- Interactive game board
- Save & replay games
- Per-player timers
- Real RL-trained opponent
- Mobile responsive

Slide 3: Architecture
- Frontend: HTML5 + Browser APIs
- Backend: FastAPI (Python)
- Logic: Shared game engine
- AI: Trained RL models (Stable Baselines3)

Slide 4: Tech Stack
- Python 3.12
- FastAPI 0.136
- PyTorch 2.11
- Gymnasium 1.2
- Stable Baselines3 2.8

[Live Demo Here]

Slide 5: Summary
- Production-ready for demos
- Extensible architecture
- Error resilience
- Full game preservation
```

---

## Timing Checklist

- [ ] Server started 2 min before demo
- [ ] Browser pre-loaded at http://localhost:7890
- [ ] Clear the browser cache (Ctrl+Shift+Delete)
- [ ] Have a backup model selected (not stage12 if slow)
- [ ] Notebook open to show code if needed
- [ ] Phone/tablet ready to show mobile responsiveness
- [ ] Watch silence: Avoid talking during AI move (let it think)

---

**Remember**: The demo is about showing what's *possible*, not proving it's perfect. Focus on the 3-4 coolest features and let the UI speak for itself. 🦆

Good luck at finals! 🎓
