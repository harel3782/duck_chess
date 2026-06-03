# Headless Peter Training Guide

## Overview

The **headless training script** (`train_peter_headless.py`) allows you to train a Duck Chess RL agent against the Peter engine without any GUI. It's designed to:

✓ Run without pygame or X11 (works on servers, without display)
✓ Run with screen off / terminal closed (true background mode)
✓ Track exact step counts and training progress
✓ Resume from checkpoints if interrupted
✓ Log detailed metrics to CSV and TensorBoard

## Quick Start

### Start a fresh training run

```bash
python DuckChess_Game/SBThree/train_peter_headless.py \
  --steps 10_000_000 \
  --depths 1 2 3 3 \
  --checkpoint-every 200_000
```

This will:
1. Create 4 parallel environments with Peter depths 1, 2, 3, 3
2. Train for 10 million environment steps
3. Save checkpoints every 200k steps
4. Log progress to `logs/peter_training_progress.csv`
5. Save TensorBoard events to `logs/tensorboard_logs/`

### View training progress

While training is running (or after it finishes):

```bash
# Show last 10 log entries
python DuckChess_Game/SBThree/train_peter_headless.py --show-progress

# Or tail the CSV directly
tail -f logs/peter_training_progress.csv
```

### Resume interrupted training

If training is interrupted (power loss, SSH disconnect, etc.):

```bash
# Automatically resume from the latest checkpoint
python DuckChess_Game/SBThree/train_peter_headless.py --auto-resume

# Or manually specify a checkpoint
python DuckChess_Game/SBThree/train_peter_headless.py \
  --checkpoint models/duck_ppo/peter_headless/peter_v5.zip
```

## Running in the Background

### Linux / Mac (using `nohup`)

```bash
# Start training, immune to terminal closure
nohup python DuckChess_Game/SBThree/train_peter_headless.py \
  --steps 20_000_000 \
  --checkpoint-every 500_000 \
  > training.log 2>&1 &

# Get the process ID
echo $!

# Check progress
tail -f logs/peter_training_progress.csv

# Kill the job later (if needed)
kill <PID>
```

### Windows (using `pythonw`)

```cmd
REM Run without a console window (truly backgrounded)
pythonw DuckChess_Game/SBThree/train_peter_headless.py ^
  --steps 20_000_000 ^
  --checkpoint-every 500_000

REM Check progress (run in a new cmd/PowerShell)
type logs\peter_training_progress.csv
```

### Windows (using PowerShell background job)

```powershell
# Start training as a background job
$job = Start-Job -ScriptBlock {
  cd C:\Users\afiks\Documents\Afik\Afeka\duck_chess-master\duck_chess-master
  python DuckChess_Game/SBThree/train_peter_headless.py --steps 20_000_000
}

# Check job status
Get-Job

# View last 10 progress lines anytime
Get-Content logs/peter_training_progress.csv -Tail 10

# Stop the job (if needed)
Stop-Job -Job $job
```

### Docker / Remote Server

```bash
# SSH into your server
ssh user@server

# Start training detached (survives SSH disconnect)
screen -S peter_train
  python DuckChess_Game/SBThree/train_peter_headless.py --steps 30_000_000
  # Press Ctrl+A, then D to detach

# Re-attach later
screen -r peter_train

# Check progress without attaching
ssh user@server "tail -f /path/to/logs/peter_training_progress.csv"
```

## Configuration Options

### Peter Engine Depths

The `--depths` argument controls the search depth for each parallel environment.

```bash
# Recommended for quick training (faster, weaker opponent)
--depths 1 2 3 3

# Balanced (default)
--depths 1 2 3 3

# For very strong training (slower, stronger opponent)
--depths 2 3 4 4

# Single strong environment (very slow)
--depths 5
```

Approximate latencies per move at starting position:
- Depth 1: ~1 ms (very fast, lower quality)
- Depth 2: ~6 ms
- Depth 3: ~15 ms (good balance)
- Depth 4: ~4 seconds
- Depth 5: ~40 seconds (analysis)

### Training Steps

```bash
# Quick test run
--steps 1_000_000

# Standard run
--steps 10_000_000

# Long run
--steps 20_000_000

# Extended run (use when leaving for hours)
--steps 50_000_000
```

### Checkpoint Frequency

```bash
# Save frequently (for quick recovery)
--checkpoint-every 100_000

# Balanced (default)
--checkpoint-every 200_000

# Save rarely (if disk space is limited)
--checkpoint-every 500_000
```

## Understanding the Progress Log

The CSV file has these columns:

```
timestamp,total_steps,elapsed_seconds,steps_per_second,mean_reward,mean_length,checkpoint_saved
2026-05-30T10:15:23.456789,10000,45,222.22,-0.5231,487.3,NO
2026-05-30T10:15:28.789012,20000,50,400.00,-0.4156,512.1,NO
2026-05-30T10:16:14.234567,200000,296,675.68,-0.1203,604.2,YES
```

- **total_steps**: How many environment steps have completed
- **elapsed_seconds**: Wall-clock time since training started
- **steps_per_second**: Training throughput (higher = faster)
- **mean_reward**: Average episode reward (-1 to +1)
- **mean_length**: Average episode length in steps
- **checkpoint_saved**: "YES" if a model checkpoint was saved at this step

## Example: Full Day of Training

```bash
# Start training early morning, targeting 50M steps
python DuckChess_Game/SBThree/train_peter_headless.py \
  --steps 50_000_000 \
  --depths 1 2 3 3 \
  --checkpoint-every 500_000 \
  &

# Come back several hours later to check progress
python DuckChess_Game/SBThree/train_peter_headless.py --show-progress

# See that 15M steps have completed in 6 hours
# Continue monitoring periodically
tail -f logs/peter_training_progress.csv

# When done, the final model is saved to:
# models/duck_ppo/peter_headless/peter_headless_final.zip
```

## TensorBoard Monitoring

While training runs, you can monitor detailed metrics:

```bash
# In a separate terminal
tensorboard --logdir logs/tensorboard_logs

# Open http://localhost:6006 in your browser
```

Tracked metrics:
- Episode reward
- Episode length
- Loss
- Entropy
- Policy gradient
- Value function loss

## Performance Expectations

On a typical modern machine (Intel i7 + RTX 3080):

| Config | Steps/Sec | 10M Steps | 50M Steps |
|--------|-----------|-----------|-----------|
| 4 envs, depths (1,2,3,3) | ~650 | 4.3 hours | 21 hours |
| 8 envs, depths (1,2,3,3) | ~950 | 2.9 hours | 14.6 hours |
| 4 envs, depths (2,3,4,4) | ~400 | 7 hours | 35 hours |

## Troubleshooting

### Training is slow
- Check `steps_per_second` in the CSV
- Verify Peter engine is working: `python -c "import engine; e = engine.Engine(); print('OK')"`
- Check CPU/GPU usage during training

### Training crashes
- Check `logs/peter_training_<timestamp>.log` for error details
- Reduce `n_envs` if out of memory
- Ensure tensorflow/torch are properly installed

### Progress file not updating
- Check that the process is still running: `ps aux | grep train_peter_headless`
- Verify disk space: `df -h logs/`
- Check file permissions

### Can't resume from checkpoint
```bash
# List available checkpoints
ls -la models/duck_ppo/peter_headless/

# Resume from specific one
python DuckChess_Game/SBThree/train_peter_headless.py \
  --checkpoint models/duck_ppo/peter_headless/peter_headless_v5.zip
```

## Tips for Long Runs

1. **Use `--auto-resume`**: If interrupted, training will pick up from the latest checkpoint
2. **Monitor periodically**: Check progress every few hours with `--show-progress`
3. **Keep logs**: The CSV is valuable for training analysis
4. **Backup models**: Periodically copy `models/duck_ppo/peter_headless/` to external storage
5. **Adjust depths based on compute**: Use lower depths if you need faster training

## Next Steps

Once training completes (or whenever you want to use the model):

1. Copy the final model:
   ```bash
   cp models/duck_ppo/peter_headless/peter_headless_final.zip \
      models/duck_ppo/peter_best_vs_peter.zip
   ```

2. Load it in the UI:
   - Edit `DuckChess_Game/UI/main.py` and update the model path

3. Evaluate against Peter:
   ```bash
   python DuckChess_Game/SBThree/train.py play --games 10
   ```

4. Analyze training in TensorBoard:
   ```bash
   tensorboard --logdir logs/tensorboard_logs
   ```
