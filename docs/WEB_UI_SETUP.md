# Duck Chess Web UI - Setup & Requirements

## Quick Start

```bash
# 1. Ensure you're in the project root
cd /path/to/duck_chess

# 2. Create and activate virtual environment (if not already done)
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# OR
.venv\Scripts\activate             # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the web server
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890

# 5. Open browser and navigate to:
# http://localhost:7890
```

## System Requirements

- **Python**: 3.12 or higher
- **OS**: Windows, macOS, or Linux
- **Disk Space**: ~1GB (mostly for trained models in `models/`)
- **Memory**: 4GB+ RAM recommended
- **GPU**: Not required (CPU mode is supported)

## Dependencies Overview

### Core Web Framework
- **fastapi** (0.136.3): Modern async web framework
- **uvicorn** (0.49.0): ASGI web server
- **pydantic** (2.13.4): Data validation

### Machine Learning & Game Engine
- **stable-baselines3** (2.8.0): RL algorithm library (MaskablePPO)
- **sb3-contrib** (2.8.0): Contrib algorithms (MaskablePPO implementation)
- **gymnasium** (1.2.0): Game environment framework
- **torch** (2.11.0): Deep learning framework (CPU by default)
- **numpy** (2.4.0): Numerical computing

### Optional (For Desktop UI)
- **pygame** (2.6.0): Desktop game engine (only needed if running `DuckChess_Game/UI/main.py`)

### Testing (Optional)
- **pytest** (7.4.3): Test runner
- **pytest-cov** (4.1.0): Coverage reporting

## Installation Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'gymnasium'`
**Solution**: Make sure you've run `pip install -r requirements.txt` and are using the activated virtual environment.

### Issue: `torch` installation fails
**Solution**: 
- For CPU only (recommended): Use the default from requirements.txt
- For GPU (NVIDIA CUDA): Replace `torch==2.11.0` with the appropriate CUDA-enabled version from pytorch.org
  ```bash
  pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu118
  ```

### Issue: Port 7890 already in use
**Solution**: Use a different port:
```bash
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 8000
```

### Issue: Permission denied on `.venv\Scripts\activate` (Windows PowerShell)
**Solution**: Run PowerShell as administrator, or use:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Project Structure

```
duck_chess/
├── web_ui/                    # Web UI (FastAPI + HTML/CSS/JS)
│   ├── server.py              # FastAPI backend
│   ├── index.html             # Single-page frontend
│   └── duck.png               # Asset (favicon, UI image)
├── DuckChess_Game/            # Game engine (DO NOT MODIFY)
│   ├── Logic/                 # Pure Python game logic
│   ├── UI/                    # Pygame desktop UI
│   └── SBThree/               # RL training pipeline
├── models/duck_ppo/           # Trained model checkpoints (.zip files)
├── saved_replays/             # User-saved games (JSON)
├── requirements.txt           # Python dependencies
└── CLAUDE.md                  # Project documentation
```

## Running the Web UI

### Standard Start
```bash
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
```

### With Auto-Reload (Development)
```bash
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890 --reload
```

### Headless Mode (Background)
```bash
nohup python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890 &
# or on Windows:
START /B python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
```

## Testing the Installation

After starting the server, test these endpoints:

```bash
# Check if server is running
curl http://localhost:7890/

# List available models
curl http://localhost:7890/api/models
```

Expected response from `/api/models`:
```json
{
  "models": [
    {"id": "stage11", "label": "Duck PPO — Stage 11"},
    {"id": "stage10", "label": "Duck PPO — Stage 10 (league)"},
    ...
  ]
}
```

## Browser Compatibility

- **Chrome/Edge**: ✅ Full support
- **Firefox**: ✅ Full support
- **Safari**: ✅ Full support (iOS 12+)
- **Internet Explorer**: ❌ Not supported (use modern browser)

## Performance Notes

- **First load**: 2-3 seconds (model loading from disk)
- **AI move generation**: 0.5-2 seconds depending on model
- **Saved game load**: <1 second
- **Replay navigation**: Instant (board snapshots pre-generated)

## Updating Dependencies

To update all packages to their latest versions:
```bash
pip install --upgrade -r requirements.txt
```

To update just one package:
```bash
pip install --upgrade fastapi
```

## Running Both UIs

You can run both the Web UI and Pygame UI simultaneously:

```bash
# Terminal 1: Web UI
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890

# Terminal 2: Pygame UI
python DuckChess_Game/UI/main.py
```

Both share the same game logic and trained models.

## Troubleshooting Checklist

- [ ] Python 3.12+ installed: `python --version`
- [ ] Virtual environment activated: `which python` shows `.venv/...`
- [ ] Dependencies installed: `pip list | grep fastapi`
- [ ] Port 7890 available: `netstat -an | grep 7890` (or `Get-NetTCPConnection` on Windows)
- [ ] Models present: `ls models/duck_ppo/` has `.zip` files
- [ ] Server running: `curl http://localhost:7890/ ` returns HTML

## Support & Documentation

- **Project docs**: See [CLAUDE.md](CLAUDE.md) for architecture overview
- **API docs**: Navigate to `http://localhost:7890/docs` when server is running (Swagger UI)
- **Game rules**: In-app Rules modal or CLAUDE.md "Duck Chess Rules" section

---

**Last updated**: 2026-06-14
**Web UI Version**: 1.0 (15 tasks, fully polished)
