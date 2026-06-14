#!/usr/bin/env python
import pickle
from pathlib import Path

replay_dir = Path("saved_replays/peter_d2")
pkl_file = list(replay_dir.glob("*.pkl"))[0]

print(f"Inspecting: {pkl_file.name}\n")

with open(pkl_file, 'rb') as f:
    replay = pickle.load(f)

print(f"Type: {type(replay)}")
print(f"Keys: {list(replay.keys()) if isinstance(replay, dict) else 'N/A (not a dict)'}")
print(f"\nContent:")
print(replay)
