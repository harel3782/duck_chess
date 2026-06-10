# Headless Peter Training Guide

[`train_peter_headless.py`](DuckChess_Game/SBThree/train_peter_headless.py) trains a Duck Chess RL
agent against the local **Peter** engine with **no GUI**. It's built for long, unattended runs:

- Runs without pygame or a display (servers, CI, screen off / terminal closed).
- Tracks exact step counts and throughput to a CSV you can read any time.
- Resumes from checkpoints if a run is interrupted.
- Logs detailed metrics to TensorBoard.

## Where things go

| Output | Default path | Override |
|--------|--------------|----------|
| Progress CSV | `logs/peter_training_progress.csv` | `--log-dir` |
| TensorBoard events | `logs/tensorboard_logs/` | `--log-dir` |
| Checkpoints | `models/duck_ppo/peter_headless/` | `--model-dir` |
| Final model | `models/duck_ppo/peter_headless/peter_headless_final.zip` | — |

## Command-line options

| Flag | Default | Purpose |
|------|---------|---------|
| `--steps` | `10_000_000` | Total training timesteps |
| `--depths` | `1 2 3 3` | Peter search depth per parallel environment (one int per env) |
| `--checkpoint-every` | `200_000` | Save a checkpoint every N steps |
| `--checkpoint PATH` | — | Resume from a specific checkpoint |
| `--auto-resume` | off | Resume from the latest checkpoint found in `--model-dir` |
| `--show-progress` | off | Print recent progress and exit (no training) |
| `--log-dir` | `logs` | Directory for the CSV and TensorBoard events |
| `--model-dir` | `models/duck_ppo/peter_headless` | Directory for checkpoints |

## Quick start

### Start a fresh run
```bash
python DuckChess_Game/SBThree/train_peter_headless.py \
  --steps 10_000_000 \
  --depths 1 2 3 3 \
  --checkpoint-every 200_000
```
This creates 4 parallel environments (Peter depths 1, 2, 3, 3), trains for 10M steps, checkpoints
every 200k steps, and logs to `logs/`.

### View progress
```bash
# Print the last few log entries and exit
python DuckChess_Game/SBThree/train_peter_headless.py --show-progress

# Or follow the CSV directly
#   Linux/macOS:
tail -f logs/peter_training_progress.csv
#   PowerShell:
Get-Content logs/peter_training_progress.csv -Tail 10 -Wait
```

### Resume an interrupted run
```bash
# Resume from the latest checkpoint automatically
python DuckChess_Game/SBThree/train_peter_headless.py --auto-resume

# Or point at a specific checkpoint
python DuckChess_Game/SBThree/train_peter_headless.py \
  --checkpoint models/duck_ppo/peter_headless/peter_headless_v5.zip
```

## Running in the background

This is a Windows-first project, so the PowerShell recipes come first.

### Windows — PowerShell background job
```powershell
$job = Start-Job -ScriptBlock {
  Set-Location C:\Users\afiks\Documents\Afik\Afeka\duck_chess-master\duck_chess-master
  python DuckChess_Game/SBThree/train_peter_headless.py --steps 20_000_000
}

Get-Job                                                   # check status
Get-Content logs/peter_training_progress.csv -Tail 10     # check progress anytime
Stop-Job -Job $job                                        # stop it later
```

### Windows — `pythonw` (no console window)
```bat
pythonw DuckChess_Game/SBThree/train_peter_headless.py ^
  --steps 20_000_000 ^
  --checkpoint-every 500_000

REM Check progress from any new terminal
type logs\peter_training_progress.csv
```

### Linux / macOS — `nohup`
```bash
nohup python DuckChess_Game/SBThree/train_peter_headless.py \
  --steps 20_000_000 \
  --checkpoint-every 500_000 \
  > logs/peter_train.log 2>&1 &

echo $!                                   # the process ID
tail -f logs/peter_training_progress.csv  # follow progress
kill <PID>                                # stop it later
```

### Remote server — `screen`
```bash
ssh user@server
screen -S peter_train
  python DuckChess_Game/SBThree/train_peter_headless.py --steps 30_000_000
  # Ctrl+A then D to detach
screen -r peter_train                                       # re-attach later
ssh user@server "tail -f /path/to/logs/peter_training_progress.csv"
```

## Tuning the run

### Peter engine depths (`--depths`)
One integer per parallel environment. Deeper = stronger and slower. Approximate latency per move
at the starting position:

| Depth | Latency / move | Notes |
|-------|----------------|-------|
| 1 | ~1 ms | Very fast, weak; the policy can exploit its 1-ply horizon |
| 2 | ~6 ms | Fast, a solid tactical anchor |
| 3 | ~15 ms | Good balance; defends its king, punishes the king-rush |
| 4 | ~4 s | Very slow |
| 5 | ~40 s | Analysis only |

```bash
--depths 1 2 3 3   # default — mixed, fast throughput
--depths 2 3 4 4   # stronger opponent, slower
--depths 5         # single very strong (very slow) env
```

> **Note:** `SubprocVecEnv` is synchronous — the batch advances at the speed of the *slowest*
> environment. Mixing a depth-5 env with three depth-1 envs gates the whole batch on depth-5.

### Steps and checkpoint frequency
```bash
--steps 1_000_000          # quick test
--steps 10_000_000         # standard run
--steps 50_000_000         # extended, multi-hour run

--checkpoint-every 100_000  # frequent (fast recovery)
--checkpoint-every 500_000  # infrequent (saves disk)
```

## Reading the progress log

The CSV columns:

```
timestamp,total_steps,elapsed_seconds,steps_per_second,mean_reward,mean_length,checkpoint_saved
2026-05-30T10:15:23.456789,10000,45,222.22,-0.5231,487.3,NO
2026-05-30T10:16:14.234567,200000,296,675.68,-0.1203,604.2,YES
```

| Column | Meaning |
|--------|---------|
| `total_steps` | Cumulative environment steps completed |
| `elapsed_seconds` | Wall-clock time since training started |
| `steps_per_second` | Throughput (higher = faster) |
| `mean_reward` | Rolling average episode reward (−1 to +1) |
| `mean_length` | Rolling average episode length, in steps |
| `checkpoint_saved` | `YES` if a checkpoint was written at this step |

`mean_reward` showing `N/A` during the first steps is normal — SB3 statistics build up over time.

## TensorBoard

```bash
tensorboard --logdir logs/tensorboard_logs
# open http://localhost:6006
```
Tracked metrics include episode reward and length, loss, entropy, policy gradient, and value loss.

## Approximate performance

On a modern machine (Intel i7 + RTX 3080, CPU PyTorch is fine for this network):

| Config | Steps/sec | 10M steps | 50M steps |
|--------|-----------|-----------|-----------|
| 4 envs, depths (1,2,3,3) | ~650 | ~4.3 h | ~21 h |
| 8 envs, depths (1,2,3,3) | ~950 | ~2.9 h | ~14.6 h |
| 4 envs, depths (2,3,4,4) | ~400 | ~7 h | ~35 h |

## Troubleshooting

**Training is slow**
Check `steps_per_second` in the CSV. Confirm the Peter engine imports, and lower `--depths` if the
deepest env is gating the batch.

**Out of memory**
Reduce the number of environments (fewer entries in `--depths`).

**Progress file not updating**
Make sure the process is still alive (`Get-Job` / `ps aux | grep train_peter_headless`), and check
disk space and permissions on `--log-dir`.

**Can't resume**
List checkpoints in `models/duck_ppo/peter_headless/` and pass one explicitly with `--checkpoint`.

## After training

1. Evaluate against the real engine — the metric that matters:
   ```bash
   python DuckChess_Game/SBThree/eval_vs_peter.py
   ```
2. To use the model in the UI, set `model_path` in
   [`DuckChess_Game/UI/main.py`](DuckChess_Game/UI/main.py) to the checkpoint path.
3. Compare runs in TensorBoard: `tensorboard --logdir logs/tensorboard_logs`.

See [training_log.md](training_log.md) for the stage-by-stage history and
[TESTING.md](TESTING.md) for engine tests.
