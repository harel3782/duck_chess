# Testing Guide

## Unit Tests

Duck Chess includes comprehensive unit tests for game logic validation.

### Running Tests

**Run all tests:**
```bash
pytest DuckChess_Game/Logic/test_logic.py -v
```

**Run with coverage report:**
```bash
pytest DuckChess_Game/Logic/test_logic.py --cov=DuckChess_Game.Logic --cov-report=html
```

**Run specific test class:**
```bash
pytest DuckChess_Game/Logic/test_logic.py::TestGameInitialization -v
```

**Run specific test:**
```bash
pytest DuckChess_Game/Logic/test_logic.py::TestGameInitialization::test_init_standard_position -v
```

### Test Coverage

The test suite (`test_logic.py`) includes 19 test classes covering:

| Class | Purpose | Key Tests |
|-------|---------|-----------|
| `TestGameInitialization` | Game setup | Initial position, board dimensions, piece placement |
| `TestPhaseManagement` | Two-phase system | Phase transitions, turn increments |
| `TestDuckRules` | Duck mechanics | Placement rules, blocking behavior |
| `TestMoveLegality` | Move validation | Pawn/knight moves, legal move generation |
| `TestObservationEncoding` | RL observation | 19-channel tensor shape, board state reflection |
| `TestActionMasking` | RL action mask | Mask shape, legal move tracking |
| `TestEndgame` | Game termination | Checkmate, check, stalemate, draw detection |
| `TestGameState` | State management | Save/load, move history tracking |
| `TestIntegration` | Full games | Multi-move sequences, game flow |

### Installing Test Dependencies

```bash
pip install pytest pytest-cov
```

### Continuous Integration

After any changes to `DuckChess_Game/Logic/`, run:
```bash
pytest DuckChess_Game/Logic/test_logic.py -v --tb=short
```

## Training Validation

### Headless Peter Training

For long-running training without GUI interference:

```bash
# Start training and track progress
python DuckChess_Game/SBThree/train_peter_headless.py --steps 10_000_000

# Monitor progress in real-time
tail -f logs/peter_training_progress.csv

# Check progress without running tail
python DuckChess_Game/SBThree/train_peter_headless.py --show-progress
```

### Progress Tracking

The headless trainer logs to CSV with these columns:
- `timestamp` — when the log entry was written
- `total_steps` — cumulative environment steps
- `elapsed_seconds` — wall-clock time since training start
- `steps_per_second` — throughput metric
- `mean_reward` — rolling average reward
- `mean_length` — mean episode length
- `checkpoint_saved` — "YES" when a model checkpoint was saved

Example progress file:
```
timestamp,total_steps,elapsed_seconds,steps_per_second,mean_reward,mean_length,checkpoint_saved
2026-05-30T10:15:23.456789,10000,45,222.22,-0.5231,487.3,NO
2026-05-30T10:15:28.789012,20000,50,400.00,-0.4156,512.1,NO
2026-05-30T10:16:14.234567,200000,296,675.68,-0.1203,604.2,YES
```

### Background Training (Screen Off)

The headless trainer is designed to work with the screen off or terminal closed:

**Linux/Mac (nohup):**
```bash
nohup python DuckChess_Game/SBThree/train_peter_headless.py \
  --steps 20_000_000 \
  --checkpoint-every 500_000 \
  > training.log 2>&1 &

# Check progress
tail -f logs/peter_training_progress.csv
```

**Windows (pythonw):**
```bash
# Run without console window
pythonw DuckChess_Game/SBThree/train_peter_headless.py --steps 20_000_000

# Check progress
type logs\peter_training_progress.csv
```

**Windows (PowerShell background job):**
```powershell
$job = Start-Job -ScriptBlock {
  python DuckChess_Game/SBThree/train_peter_headless.py --steps 20_000_000
}

# Check progress anytime
Get-Content logs/peter_training_progress.csv -Tail 5
```

### Resuming Training

If training is interrupted (power loss, network issue, etc.):

```bash
# Resume from latest checkpoint
python DuckChess_Game/SBThree/train_peter_headless.py --auto-resume

# Or specify checkpoint explicitly
python DuckChess_Game/SBThree/train_peter_headless.py \
  --checkpoint models/duck_ppo/peter_headless/peter_v5.zip
```

### TensorBoard Monitoring

While training runs, monitor metrics in TensorBoard:

```bash
tensorboard --logdir logs/tensorboard_logs
```

Then open http://localhost:6006 in your browser.

## Performance Benchmarks

Expected performance on Intel i7 / RTX 3080:

| Configuration | Steps/Second | Time for 10M steps |
|---------------|-------------|-------------------|
| 4 envs, depths (1,2,3,3) | ~600-700 | 4-5 hours |
| 8 envs, depths (1,2,3,3) | ~900-1100 | 2.5-3 hours |
| Single env, depth 3 | ~150-200 | 14+ hours |

The headless trainer with 4 environments is recommended for background runs.

## Troubleshooting

### Tests fail with import errors
```bash
pip install -e .
pytest DuckChess_Game/Logic/test_logic.py -v
```

### Training crashes due to memory
Reduce `n_envs` or decrease environment batch size in `train_peter_headless.py`.

### Progress file shows N/A for mean_reward
This is normal during initial steps; SB3 statistics build up over time.

### Training is slower than expected
- Check `steps_per_second` in progress CSV
- Verify Peter engine is compiled (check for `engine` module)
- Monitor CPU/GPU usage during training
