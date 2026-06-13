#!/usr/bin/env python
import pickle
from pathlib import Path

replay_dir = Path("saved_replays/peter_d2")
pkl_files = sorted(replay_dir.glob("*.pkl"), reverse=True)[:5]

print(f"\n{'='*70}")
print(f"RECENT GAMES FROM TRAINING")
print(f"{'='*70}\n")

for i, pkl_file in enumerate(pkl_files, 1):
    try:
        with open(pkl_file, 'rb') as f:
            replay = pickle.load(f)

        actions = replay.get('actions', [])
        learning_color = replay.get('learning_color', 'white')

        print(f"Game {i}: {pkl_file.name}")
        print(f"  Agent color: {learning_color}")
        print(f"  Total moves: {len(actions)}")
        print(f"  Actions: {actions[:20]}")  # First 20 actions
        print()
    except Exception as e:
        print(f"Error reading {pkl_file}: {e}\n")

print(f"{'='*70}")
print(f"Total replay files: {len(list(replay_dir.glob('*.pkl')))}")
