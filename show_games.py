#!/usr/bin/env python
"""Decode and display replay games."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pickle
from pathlib import Path
from DuckChess_Game.Logic.logic import DuckChess

def decode_action(action_idx):
    """Convert action index to from/to squares."""
    from_sq = (action_idx >> 6) & 0x3F
    to_sq = action_idx & 0x3F
    return from_sq, to_sq

def sq_to_coord(sq):
    """Convert square index to algebraic notation."""
    row, col = divmod(sq, 8)
    return chr(97 + col) + str(8 - row)

def show_game(pkl_file, max_moves=20):
    """Load and display a game from a replay file."""
    with open(pkl_file, 'rb') as f:
        replay = pickle.load(f)

    actions = replay.get('action_history', [])
    agent_color = replay.get('learning_color', 'w')

    # Initialize game
    game = DuckChess()
    game.set_learning_color(agent_color)

    # Replay the game
    move_strings = []
    for action_idx in actions:
        try:
            game.apply_action(action_idx)
            from_sq, to_sq = decode_action(action_idx)
            from_coord = sq_to_coord(from_sq)
            to_coord = sq_to_coord(to_sq)
            move_strings.append(f"{from_coord}→{to_coord}")
        except Exception as e:
            break

    # Get result
    winner = getattr(game, 'winner', None)
    result_map = {
        'w': 'W',
        'b': 'L',
        'draw': '=',
        None: '?'
    }

    if agent_color == 'b':
        result_map = {'w': 'L', 'b': 'W', 'draw': '=', None: '?'}

    result = result_map.get(winner, '?')

    # Format output
    moves_display = " ".join(move_strings[:max_moves])
    if len(move_strings) > max_moves:
        moves_display += f" ... ({len(move_strings)} total)"

    return {
        'file': pkl_file.name,
        'agent': agent_color,
        'result': result,
        'moves': len(move_strings),
        'moves_str': moves_display
    }

# Show recent games
replay_dir = Path("saved_replays/peter_d2")
pkl_files = sorted(replay_dir.glob("*.pkl"), reverse=True)[:10]

print(f"\n{'='*80}")
print(f"RECENT GAMES FROM TRAINING (Peter depth-2)")
print(f"{'='*80}\n")

for i, pkl_file in enumerate(pkl_files, 1):
    try:
        game_info = show_game(pkl_file, max_moves=10)
        print(f"[{i:>2}] {game_info['agent'].upper()}{game_info['result']} | {game_info['moves']:>3} moves | {game_info['moves_str']}")
    except Exception as e:
        print(f"[{i:>2}] Error: {e}")

print(f"\n{'='*80}")
