#!/usr/bin/env python
"""
watch_replays.py — Watch training games in real-time as replays are saved.

Monitors the saved_replays directory and displays each new game's moves
in a human-readable format.

Usage:
  python watch_replays.py --stage real_replays_d3

  # Or just watch the directory continuously:
  python watch_replays.py --stage real_replays_d3 --watch
"""
import os
import sys
import pickle
import time
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from DuckChess_Game.Logic.logic import DuckChess

def format_move(from_sq, to_sq, piece_type=None, captured=None):
    """Format a move in algebraic notation."""
    def sq_to_coord(sq):
        row, col = divmod(sq, 8)
        return chr(97 + col) + str(8 - row)

    from_coord = sq_to_coord(from_sq)
    to_coord = sq_to_coord(to_sq)

    piece_str = ""
    if piece_type:
        piece_str = piece_type.upper() if piece_type != 'p' else ""

    capture_str = "x" if captured else "-"

    return f"{from_coord}{capture_str}{to_coord}"

def decode_replay(replay_file):
    """Load and decode a replay file."""
    try:
        with open(replay_file, 'rb') as f:
            replay = pickle.load(f)
        return replay
    except Exception as e:
        print(f"  ✗ Error loading {replay_file}: {e}")
        return None

def narrate_game(replay_data):
    """Convert replay data to move sequence."""
    if not isinstance(replay_data, dict):
        return None

    # Extract the key fields
    actions = replay_data.get('actions', [])
    learning_color = replay_data.get('learning_color', 'white')

    if not actions:
        return "  (empty replay)"

    # Initialize game
    game = DuckChess()
    game.set_learning_color(learning_color)

    moves_str = []
    agent_moves = []

    try:
        for action_idx in actions:
            # Get the move before applying
            from_sq = (action_idx >> 6) & 0x3F
            to_sq = action_idx & 0x3F

            # Apply the action
            game.apply_action(action_idx)

            # Record if it's an agent move
            if game.phase == "place_duck" or len(agent_moves) > 0:
                agent_moves.append(action_idx)
                if game.phase == "move_piece":
                    from_row, from_col = divmod(from_sq, 8)
                    to_row, to_col = divmod(to_sq, 8)
                    piece = game.board[from_row][from_col]
                    move_str = format_move(from_sq, to_sq, piece)
                    moves_str.append(move_str)

        winner = getattr(game, 'winner', None)
        result = {
            'winner': winner,
            'moves': agent_moves,
            'move_str': " ".join(moves_str[:10]) + ("..." if len(moves_str) > 10 else ""),
            'total_moves': len(agent_moves),
        }
        return result
    except Exception as e:
        return f"  ✗ Error: {e}"

def watch_directory(stage_name, watch=False):
    """Monitor and display replays."""
    replay_dir = Path("saved_replays") / stage_name

    print(f"\n{'='*70}")
    print(f"Watching: {replay_dir}")
    print(f"{'='*70}\n")

    seen_files = set()
    game_count = 0

    while True:
        if replay_dir.exists():
            pkl_files = sorted(replay_dir.glob("*.pkl"))
            new_files = [f for f in pkl_files if f.name not in seen_files]

            for replay_file in new_files:
                seen_files.add(replay_file.name)
                game_count += 1

                print(f"[Game {game_count}] {replay_file.name}")

                replay_data = decode_replay(replay_file)
                if replay_data:
                    result = narrate_game(replay_data)
                    if isinstance(result, dict):
                        winner = result['winner']
                        total = result['total_moves']
                        moves = result['move_str']

                        result_str = {
                            'draw': '=',
                            'white': 'W',
                            'black': 'L' if hasattr(narrate_game, '_agent_is_black') else 'W',
                            None: '?',
                        }.get(winner, '?')

                        print(f"  Result: {result_str}  Moves: {total}  {moves}\n")
                    else:
                        print(f"  {result}\n")
        else:
            print(f"  Waiting for {replay_dir} to be created...")

        if not watch:
            break

        time.sleep(2)

def main():
    p = argparse.ArgumentParser(description="Watch Duck Chess training replays in real-time")
    p.add_argument("--stage", default="real_replays_d3", help="Replay directory stage name")
    p.add_argument("--watch", action="store_true", help="Keep watching for new replays (continuous)")
    args = p.parse_args()

    watch_directory(args.stage, watch=args.watch)

if __name__ == "__main__":
    main()
