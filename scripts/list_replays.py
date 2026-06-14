import pickle
from pathlib import Path

replay_dir = Path("saved_replays/peter_d2")
pkl_files = sorted(replay_dir.glob("*.pkl"), reverse=True)[:10]

print(f"\n{'='*80}")
print(f"RECENT TRAINING GAMES")
print(f"{'='*80}\n")

for i, pkl_file in enumerate(pkl_files, 1):
    with open(pkl_file, 'rb') as f:
        replay = pickle.load(f)

    actions = replay.get('action_history', [])
    agent_color = str(replay.get('learning_color', 'w')).strip()

    # Show first 20 actions
    actions_str = str(actions[:20])
    if len(actions) > 20:
        actions_str = str(actions[:20]) + f" ... ({len(actions)} total)"

    print(f"[{i}] Agent: {agent_color.upper()}  Moves: {len(actions):>3}  {actions_str}")

print(f"\n{'='*80}")
print(f"Total replays: {len(list(replay_dir.glob('*.pkl')))}")
print(f"Location: saved_replays/peter_d2/")
print(f"{'='*80}\n")
